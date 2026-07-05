"""End-to-end ngspice integration tests for the behavioral detector.

These run real simulations. Select them with:

    pytest -m integration

The detector benches use the behavioral MCP6561 equivalent
(``eod_comparator_behavioral.inc``), so every configuration here is
expected to converge deterministically on the first try — there are no
retries. The Microchip vendor macromodel was retired from transient
benches because its ESD clamp diodes collapsed the timestep
non-deterministically when cascaded with the INA333 macromodel.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

from eod_sim.comparator_network import ComparatorNetworkParams
from eod_sim.runner import RunConfig, run_simulation

PROJECT_ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice not installed"),
]


def _detector_config(
    tmp_path: Path,
    *,
    stage_id: str = "03_detector",
    bench_variant: str = "ti",
    r_comp: str = "4.7k",
    r_hyst: str = "1Meg",
    gain: float = 2.0,
    pulse_mv: float = 300.0,
    pulse_shape: str = "rounded",
    vthresh: float | None = None,
) -> RunConfig:
    return RunConfig(
        stage_id=stage_id,
        bench_variant=bench_variant,
        gain=gain,
        pulse_mv=pulse_mv,
        pulse_shape=pulse_shape,
        pulse_width_us=200.0,
        isi_ms=2.0,
        num_pulses=4,
        duration_ms=20.0,
        pulse_zoom=False,
        output_root=tmp_path,
        vthresh=vthresh,
        comparator_network=ComparatorNetworkParams(r_comp=r_comp, r_hyst=r_hyst),
    )


def _rising_edges(result) -> int:
    """Count TRIGGER rising edges through the VDD/2 midpoint."""
    trig = result.simulation.node_voltage("trigger")
    hi = (trig > 1.65).astype(int)
    return int((np.diff(hi) == 1).sum())


def test_t1_detector_low_r9_gain3(tmp_path):
    """Original user scenario: R9=1.2k, gain 3, 300 mV rounded."""
    result = run_simulation(
        _detector_config(tmp_path, r_comp="1.2k", gain=3.0), PROJECT_ROOT
    )
    assert result.quality is not None and result.quality.passed
    assert result.quality.stimulus_max_error_mv is not None
    assert result.quality.stimulus_max_error_mv < 1.0


def test_t2_detector_defaults_trigger_toggles(tmp_path):
    """Default network (R9=4.7k, gain 2): TRIGGER must swing rail to rail."""
    result = run_simulation(_detector_config(tmp_path), PROJECT_ROOT)
    assert result.quality is not None and result.quality.passed
    # 300 mV * G2 above VREF crosses the 1.85 V threshold.
    assert result.vout_min_v is not None and result.vout_min_v < 0.5
    assert result.peak_vout_v is not None and result.peak_vout_v > 3.0


def test_t3_frontend_ti_stimulus_fidelity(tmp_path):
    """Stage 02 (no comparator) at the same aggressive settings."""
    result = run_simulation(
        _detector_config(tmp_path, stage_id="02_frontend", r_comp="1.2k", gain=3.0),
        PROJECT_ROOT,
    )
    assert result.quality is not None and result.quality.passed
    assert result.quality.stimulus_max_error_mv is not None
    assert result.quality.stimulus_max_error_mv < 1.0
    # Without comparator kickback the amplifier gain is measurable cleanly.
    assert result.measured_gain is not None
    assert abs(result.measured_gain - 3.0) < 0.15
    # COMP_IN must follow ELEC_OUT through the C5/R9 filter (loaded copy).
    sim = result.simulation
    mask = sim.time_s >= 1e-3
    comp_in = sim.node_voltage("comp_in")[mask]
    elec_out = sim.node_voltage("elec_out")[mask]
    assert float(np.max(np.abs(comp_in - elec_out))) < 0.2


def test_t4_vthresh_detection_boundary(tmp_path):
    """Raising VTHRESH above the COMP_IN excursion suppresses triggering."""
    triggered = run_simulation(
        _detector_config(tmp_path / "lo", vthresh=1.85), PROJECT_ROOT
    )
    assert triggered.peak_vout_v is not None and triggered.peak_vout_v > 3.0

    quiet = run_simulation(
        _detector_config(tmp_path / "hi", vthresh=3.0), PROJECT_ROOT
    )
    # COMP_IN peaks near VREF + G*pulse ≈ 2.25 V < 3.0 V: no trigger.
    assert quiet.peak_vout_v is not None and quiet.peak_vout_v < 1.0


def test_t5_passives_lf_offset_hpf(tmp_path):
    """Slow water artifact swings the electrodes but not the INA inputs."""
    config = RunConfig(
        stage_id="01_passives",
        bench_variant="default",
        pulse_mv=1.0,
        pulse_shape="rounded",
        pulse_width_us=200.0,
        isi_ms=2.0,
        num_pulses=4,
        duration_ms=100.0,
        pulse_zoom=False,
        output_root=tmp_path,
        lf_offset_enabled=True,
        lf_offset_amplitude_mv=100.0,
        lf_offset_seed=42,
    )
    result = run_simulation(config, PROJECT_ROOT)
    assert result.quality is not None and result.quality.passed
    sim = result.simulation
    mask = sim.time_s >= 50e-3  # let the input-network HPF settle
    elec = sim.diff_pair("elec_a", "elec_b")[mask]
    ina = sim.diff_pair("ina_p", "ina_n")[mask]
    measured_ratio = float(np.max(np.abs(ina))) / float(np.max(np.abs(elec)))

    # First-order HPF prediction for the differential path:
    # C = C2 series C3 (2.35 nF), loop R = 2*R4 + (R15 || 2*R6),
    # passband divider = load / (load + 2*R4).
    c_eff = 4.7e-9 / 2
    r_load = 1 / (1 / 1e6 + 1 / 20e6)
    r_loop = 2 * 100e3 + r_load
    fc = 1 / (2 * np.pi * c_eff * r_loop)  # ~59 Hz
    f = result.lf_offset.frequency_hz
    expected_ratio = (r_load / r_loop) * (f / fc) / np.sqrt(1 + (f / fc) ** 2)

    # The simulated attenuation must match physical first-order behavior.
    assert measured_ratio < 0.6  # slow offset is attenuated at the INA inputs
    assert expected_ratio / 1.5 < measured_ratio < expected_ratio * 1.5


@pytest.mark.parametrize("pulse_shape", ["rounded", "square"])
@pytest.mark.parametrize("r_comp", ["200", "470", "1.2k", "4.7k"])
def test_detector_matrix_converges(tmp_path, r_comp, pulse_shape):
    """Full R9 x pulse-shape matrix converges deterministically at gain 3."""
    result = run_simulation(
        _detector_config(tmp_path, r_comp=r_comp, gain=3.0, pulse_shape=pulse_shape),
        PROJECT_ROOT,
    )
    assert result.quality is not None and result.quality.passed
    assert result.quality.stimulus_max_error_mv < 1.0


def test_no_chatter_one_trigger_per_pulse(tmp_path):
    """Each of the 4 supra-threshold EOD pulses produces exactly one TRIGGER
    rising edge — no chatter or retriggering."""
    result = run_simulation(_detector_config(tmp_path), PROJECT_ROOT)
    assert result.quality is not None and result.quality.passed
    assert _rising_edges(result) == 4


def test_hysteresis_r5_loading_raises_effective_threshold(tmp_path):
    """R5 is live in the model: shrinking it (stronger positive feedback)
    also pulls COMP_IN toward the low output, raising the effective rising
    threshold until this 300 mV / G2 signal no longer triggers at all."""
    default = run_simulation(_detector_config(tmp_path / "r5_1meg"), PROJECT_ROOT)
    assert _rising_edges(default) == 4

    heavy = run_simulation(
        _detector_config(tmp_path / "r5_100k", r_hyst="100k"), PROJECT_ROOT
    )
    # COMP_IN = ELEC_OUT * R5/(R5+R9) peaks at ~1.84 V < 1.85 V threshold.
    assert _rising_edges(heavy) == 0
    assert heavy.peak_vout_v is not None and heavy.peak_vout_v < 0.5


def test_ideal_bench_matches_detection(tmp_path):
    """The ideal-INA bench triggers on the same stimulus as the TI bench."""
    result = run_simulation(
        _detector_config(tmp_path, bench_variant="ideal"), PROJECT_ROOT
    )
    assert result.quality is not None and result.quality.passed
    assert _rising_edges(result) == 4
