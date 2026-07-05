"""Unit tests for post-simulation validation."""

import numpy as np

from eod_sim.results import SimulationResult
from eod_sim.stages.registry import get_stage
from eod_sim.validation import scan_ngspice_output, validate_simulation
from eod_sim.waveforms import EODPulseConfig, generate_eod_pulse_train, WaveformResult


def _result_for(stage_id: str, time_s: np.ndarray, diff: np.ndarray) -> SimulationResult:
    stage = get_stage(stage_id)
    n = len(time_s)
    elec_a = diff / 2
    elec_b = -diff / 2
    return SimulationResult(
        time_s=time_s,
        in_p=np.full(n, 1.65),
        in_n=np.full(n, 1.65),
        out=np.full(n, 1.65),
        ref=np.full(n, 1.65),
        extra={
            "src_a": elec_a,
            "src_b": elec_b,
            "elec_a": elec_a,
            "elec_b": elec_b,
            "elec_out": np.full(n, 1.65),
            "comp_in": np.full(n, 1.65),
        },
        signal_nodes=stage.resolved_signal_nodes(),
    )


def _waveform(cfg: EODPulseConfig) -> WaveformResult:
    time_s, vp, vn, lf = generate_eod_pulse_train(cfg)
    return WaveformResult(
        time_s=time_s,
        vp=vp,
        vn=vn,
        vin_diff=vp - vn,
        config=cfg,
        diff_path=None,
        lf_offset=lf,
    )


def test_clean_run_passes():
    cfg = EODPulseConfig(pulse_mv=300.0, duration_ms=20.0, drive_mode="electrodes", vcm=0.0)
    wf = _waveform(cfg)
    result = _result_for("02_frontend", wf.time_s, wf.vin_diff)
    quality = validate_simulation(result, get_stage("02_frontend"), tstop_s=20e-3, waveform=wf)
    assert quality.passed
    assert quality.stimulus_max_error_mv is not None
    assert quality.stimulus_max_error_mv < 1e-6


def test_early_abort_fails():
    cfg = EODPulseConfig(pulse_mv=300.0, duration_ms=20.0, drive_mode="electrodes", vcm=0.0)
    wf = _waveform(cfg)
    cut = len(wf.time_s) // 4
    result = _result_for("02_frontend", wf.time_s[:cut], wf.vin_diff[:cut])
    quality = validate_simulation(result, get_stage("02_frontend"), tstop_s=20e-3, waveform=wf)
    assert not quality.passed
    assert any("ended early" in e for e in quality.errors)


def test_nan_trace_fails():
    cfg = EODPulseConfig(pulse_mv=300.0, duration_ms=20.0, drive_mode="electrodes", vcm=0.0)
    wf = _waveform(cfg)
    result = _result_for("02_frontend", wf.time_s, wf.vin_diff)
    result.extra["comp_in"][10] = np.nan
    quality = validate_simulation(result, get_stage("02_frontend"), tstop_s=20e-3, waveform=wf)
    assert not quality.passed
    assert any("NaN/Inf" in e for e in quality.errors)


def test_stimulus_deviation_fails():
    cfg = EODPulseConfig(pulse_mv=300.0, duration_ms=20.0, drive_mode="electrodes", vcm=0.0)
    wf = _waveform(cfg)
    corrupted = wf.vin_diff.copy()
    corrupted[len(corrupted) // 2] += 0.05  # 50 mV glitch
    result = _result_for("02_frontend", wf.time_s, corrupted)
    quality = validate_simulation(result, get_stage("02_frontend"), tstop_s=20e-3, waveform=wf)
    assert not quality.passed
    assert any("deviates from commanded stimulus" in e for e in quality.errors)
    assert quality.stimulus_max_error_mv > 1.0


def test_scan_ngspice_output_detects_abort():
    stdout = "doAnalyses: TRAN:  Timestep too small; time = 0.005\nrun simulation(s) aborted"
    findings = scan_ngspice_output(stdout, "")
    assert "timestep too small" in findings
    assert scan_ngspice_output("all good", "") == []
