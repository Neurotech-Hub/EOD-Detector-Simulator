"""EOD-like biphasic differential pulse train waveform generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class EODPulseConfig:
    """Parameters for a biphasic differential pulse train."""

    pulse_mv: float = 1.0
    """Peak differential amplitude in millivolts."""

    phase_ms: float = 0.5
    """Duration of each lobe (positive and negative) in milliseconds."""

    isi_ms: float = 20.0
    """Inter-pulse interval in milliseconds."""

    num_pulses: int = 4
    """Number of pulses in the train."""

    vcm: float = 2.5
    """Common-mode voltage in volts."""

    start_ms: float = 5.0
    """Time of first pulse onset in milliseconds."""

    duration_ms: float = 100.0
    """Total waveform duration in milliseconds."""

    sample_us: float = 10.0
    """Sample interval in microseconds."""


@dataclass
class WaveformResult:
    """Generated differential waveform and metadata."""

    time_s: np.ndarray
    vp: np.ndarray
    vn: np.ndarray
    vin_diff: np.ndarray
    config: EODPulseConfig
    diff_path: Path


def _single_pulse_diff(t: np.ndarray, t0: float, amp: float, phase_s: float) -> np.ndarray:
    """Biphasic differential pulse: +amp, -amp, return to 0."""
    vin = np.zeros_like(t)
    t_rel = t - t0
    pos_mask = (t_rel >= 0) & (t_rel < phase_s)
    neg_mask = (t_rel >= phase_s) & (t_rel < 2 * phase_s)
    vin[pos_mask] = amp
    vin[neg_mask] = -amp
    return vin


def generate_eod_pulse_train(config: EODPulseConfig | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate time, V+, and V- arrays for an EOD-like pulse train."""
    cfg = config or EODPulseConfig()
    dt = cfg.sample_us * 1e-6
    duration_s = cfg.duration_ms * 1e-3
    time_s = np.arange(0, duration_s + dt / 2, dt)

    amp_v = cfg.pulse_mv * 1e-3
    phase_s = cfg.phase_ms * 1e-3
    isi_s = cfg.isi_ms * 1e-3
    start_s = cfg.start_ms * 1e-3

    vin_diff = np.zeros_like(time_s)
    for i in range(cfg.num_pulses):
        t0 = start_s + i * isi_s
        vin_diff += _single_pulse_diff(time_s, t0, amp_v, phase_s)

    vp = cfg.vcm + vin_diff / 2
    vn = cfg.vcm - vin_diff / 2
    return time_s, vp, vn


def write_diff_file(time_s: np.ndarray, vp: np.ndarray, vn: np.ndarray, path: Path) -> None:
    """Write ngspice filesource input: time V+ V- per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# time V+ V-\n")
        for t, v_p, v_n in zip(time_s, vp, vn):
            f.write(f"{t:.9e} {v_p:.9e} {v_n:.9e}\n")


def write_pwl(time_s: np.ndarray, voltage: np.ndarray, path: Path) -> None:
    """Write single-column PWL file (time voltage per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for t, v in zip(time_s, voltage):
            f.write(f"{t:.9e} {v:.9e}\n")


def gain_to_rg(gain: float) -> float:
    """Convert INA333 gain to RG value: G = 1 + 100k/RG."""
    if gain <= 1:
        raise ValueError("Gain must be > 1 for finite RG")
    return 100_000.0 / (gain - 1)


def format_rg_spice(rg_ohms: float) -> str:
    """Format RG value for SPICE netlist."""
    if rg_ohms >= 1000:
        return f"{rg_ohms / 1000:.4f}k"
    return f"{rg_ohms:.2f}"


def generate_and_write_pwl(
    output_dir: Path,
    config: EODPulseConfig | None = None,
) -> WaveformResult:
    """Generate EOD pulse train and write filesource waveform file."""
    cfg = config or EODPulseConfig()
    time_s, vp, vn = generate_eod_pulse_train(cfg)

    diff_path = output_dir / "input_diff.txt"
    write_diff_file(time_s, vp, vn, diff_path)

    return WaveformResult(
        time_s=time_s,
        vp=vp,
        vn=vn,
        vin_diff=vp - vn,
        config=cfg,
        diff_path=diff_path,
    )
