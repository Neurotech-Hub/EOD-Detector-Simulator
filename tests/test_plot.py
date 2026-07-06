"""Tests for plotting helpers."""

from pathlib import Path

import numpy as np
import pytest

from eod_sim.plot import PulseViewConfig, plot_single_pulse, slice_pulse_window
from eod_sim.results import SimulationResult
from eod_sim.stages.registry import get_stage
from eod_sim.waveforms import EODPulseConfig, default_sample_us, format_timestep_spice, generate_eod_pulse_train


def test_default_sample_us():
    assert default_sample_us("rounded") == 1.0
    assert default_sample_us("square") == 10.0
    recorded_us = default_sample_us("recorded")
    assert 5.0 <= recorded_us <= 5.2


def test_format_timestep_spice():
    assert format_timestep_spice(1.0) == "1u"
    assert format_timestep_spice(10.0) == "10u"
    assert format_timestep_spice(0.5) == "500n"


def test_pulse_view_window_rounded():
    cfg = EODPulseConfig(pulse_shape="rounded", pulse_width_us=200.0, start_ms=5.0)
    t_start, t_end = cfg.pulse_view_window_s()
    assert t_start == pytest.approx(0.005)
    assert t_end == pytest.approx(0.005 + 2 * 200e-6)


def test_pulse_view_window_legacy_margin():
    cfg = EODPulseConfig(pulse_shape="rounded", pulse_width_us=200.0, start_ms=5.0)
    t_start, t_end = cfg.pulse_view_window_s(margin_us=50.0)
    assert t_start == pytest.approx(0.005 - 50e-6)
    assert t_end == pytest.approx(0.005 + 200e-6 + 50e-6)


def test_slice_pulse_window():
    time_s = np.linspace(0, 0.01, 1001)
    left = 1e-3 * np.sin(2 * np.pi * 1e3 * time_s)
    right = 100e-3 * np.sin(2 * np.pi * 1e3 * time_s)
    result = SimulationResult(
        time_s=time_s,
        in_p=2.5 + left / 2,
        in_n=2.5 - left / 2,
        out=2.5 + right,
        ref=np.full_like(time_s, 2.5),
    )

    t, left_w, right_w = slice_pulse_window(result, 0.002, 0.004, left, right)
    assert len(t) > 0
    assert np.all(t >= 0.002)
    assert np.all(t <= 0.004)
    assert np.allclose(left_w, 1e-3 * np.sin(2 * np.pi * 1e3 * t))


def test_plot_single_pulse_matplotlib(tmp_path: Path):
    stage = get_stage("00_sanity_ina333")
    cfg = EODPulseConfig(
        pulse_shape="rounded",
        pulse_width_us=200.0,
        start_ms=5.0,
        duration_ms=10.0,
        sample_us=1.0,
        num_pulses=1,
    )
    time_s, vp, vn, _ = generate_eod_pulse_train(cfg)
    result = SimulationResult(
        time_s=time_s,
        in_p=vp,
        in_n=vn,
        out=cfg.vcm + (vp - vn) * 100,
        ref=np.full_like(time_s, cfg.vcm),
    )
    t_start, t_end = cfg.pulse_view_window_s()
    view = PulseViewConfig(
        pulse_onset_s=cfg.pulse_onset_s(),
        t_start_s=t_start,
        t_end_s=t_end,
    )

    out = plot_single_pulse(
        result,
        tmp_path,
        view,
        stage=stage,
        gain=100.0,
        backend="matplotlib",
        bench_variant="ideal",
    )
    assert out.is_file()
    assert out.suffix == ".png"
