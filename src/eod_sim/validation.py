"""Post-simulation quality validation for ngspice runs.

A run that produces a raw file is not necessarily trustworthy: ngspice can
abort mid-transient, emit convergence warnings, or save physically
meaningless points while fighting stiff macromodels. These checks turn those
silent failures into explicit errors so plots always reflect real circuit
behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from eod_sim.constants import OVERVIEW_TRIM_MS
from eod_sim.results import SimulationResult
from eod_sim.stages.registry import Stage
from eod_sim.waveforms import WaveformResult

STIMULUS_TOLERANCE_MV = 1.0
"""Max allowed deviation between commanded and simulated stimulus (mV)."""

DURATION_TOLERANCE = 0.99
"""Simulated end time must reach this fraction of TSTOP."""

MAX_AVG_STEP_S = 1e-3
"""Raw output must average at least one saved point per millisecond.

ngspice stores its internal (adaptive) timesteps in the raw file, not the
requested TSTEP, so the count cannot be compared against TSTOP/TSTEP. This
loose bound only catches grossly empty output from aborted runs.
"""

# Substrings in ngspice output that indicate the transient did not complete
# cleanly, even when the exit code is 0.
NGSPICE_ERROR_PATTERNS = (
    "timestep too small",
    "singular matrix",
    "transient op failed",
    "tran simulation(s) aborted",
    "simulation aborted",
    "convergence problem",
    "no convergence",
    "analysis stopped",
)


class SimulationValidationError(RuntimeError):
    """Raised when a completed ngspice run fails quality validation."""


@dataclass
class SimulationQuality:
    """Structured result of post-simulation validation."""

    passed: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stimulus_max_error_mv: float | None = None


def scan_ngspice_output(stdout: str, stderr: str) -> list[str]:
    """Return convergence/abort messages found in ngspice output."""
    findings: list[str] = []
    combined = f"{stdout}\n{stderr}".lower()
    for pattern in NGSPICE_ERROR_PATTERNS:
        if pattern in combined:
            findings.append(pattern)
    return findings


def _check_completeness(
    result: SimulationResult,
    tstop_s: float,
    errors: list[str],
) -> None:
    time_s = result.time_s
    if len(time_s) < 2:
        errors.append(f"Raw file contains only {len(time_s)} time point(s).")
        return

    t_end = float(time_s[-1])
    if t_end < tstop_s * DURATION_TOLERANCE:
        errors.append(
            f"Transient ended early at {t_end * 1e3:.3f} ms of "
            f"{tstop_s * 1e3:.3f} ms requested — ngspice aborted mid-run."
        )

    avg_step_s = t_end / len(time_s)
    if avg_step_s > MAX_AVG_STEP_S:
        errors.append(
            f"Raw file has only {len(time_s)} points over {t_end * 1e3:.1f} ms "
            f"(avg step {avg_step_s * 1e6:.0f} µs) — output is too sparse to trust."
        )

    if np.any(np.diff(time_s) <= 0):
        errors.append("Time vector is not strictly increasing — corrupt raw file.")


def _check_finite(result: SimulationResult, errors: list[str]) -> None:
    traces: dict[str, np.ndarray] = {
        "time": result.time_s,
        "in_p": result.in_p,
        "in_n": result.in_n,
        "out": result.out,
        "ref": result.ref,
    }
    traces.update(result.extra)
    for name, values in traces.items():
        if not np.all(np.isfinite(values)):
            errors.append(f"Trace '{name}' contains NaN/Inf values.")


def _check_stimulus_fidelity(
    result: SimulationResult,
    stage: Stage,
    waveform: WaveformResult,
    errors: list[str],
) -> float | None:
    # Verify at the filesource nodes (SRC_A/SRC_B), upstream of the
    # electrode impedance model: ELEC_A/ELEC_B may legitimately deviate
    # from the commanded waveform when electrode mismatch is enabled.
    pos, neg = stage.stimulus_source_nodes()
    try:
        measured = result.diff_pair(pos, neg)
    except KeyError:
        return None

    trim_s = OVERVIEW_TRIM_MS * 1e-3
    mask = result.time_s >= trim_s
    if not np.any(mask):
        return None

    # The filesource interpolates linearly between file points, so linear
    # interpolation of the ideal waveform onto the sim time base is exact.
    ideal = np.interp(result.time_s[mask], waveform.time_s, waveform.vin_diff)
    max_error_mv = float(np.max(np.abs(measured[mask] - ideal)) * 1e3)

    if max_error_mv > STIMULUS_TOLERANCE_MV:
        errors.append(
            f"Electrode differential deviates from commanded stimulus by "
            f"{max_error_mv:.2f} mV (tolerance {STIMULUS_TOLERANCE_MV:g} mV) — "
            "likely a solver failure, not physical loading. "
            "Check the run netlist and component values."
        )
    return max_error_mv


def validate_simulation(
    result: SimulationResult,
    stage: Stage,
    tstop_s: float,
    waveform: WaveformResult | None = None,
    extra_warnings: list[str] | None = None,
) -> SimulationQuality:
    """Validate a parsed simulation result against the requested run.

    Returns a SimulationQuality; callers should raise
    SimulationValidationError when quality.passed is False.
    """
    quality = SimulationQuality(warnings=list(extra_warnings or []))

    _check_completeness(result, tstop_s, quality.errors)
    _check_finite(result, quality.errors)

    if waveform is not None and stage.supports_eod_input:
        quality.stimulus_max_error_mv = _check_stimulus_fidelity(
            result, stage, waveform, quality.errors
        )

    if result.missing_probes:
        quality.warnings.append(
            "Probes missing from raw file (plotted as unavailable): "
            + ", ".join(sorted(result.missing_probes))
        )

    quality.passed = not quality.errors
    return quality
