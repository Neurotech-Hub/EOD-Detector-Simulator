"""Tests for EOD waveform generation."""

from pathlib import Path

import numpy as np
import pytest

from eod_sim.waveforms import (
    EODPulseConfig,
    format_rg_spice,
    gain_to_rg,
    generate_and_write_pwl,
    generate_eod_pulse_train,
)


def test_gain_to_rg():
    assert gain_to_rg(100) == pytest.approx(100_000 / 99, rel=1e-6)
    assert gain_to_rg(2) == pytest.approx(100_000, rel=1e-6)


def test_gain_to_rg_invalid():
    with pytest.raises(ValueError):
        gain_to_rg(1)


def test_format_rg_spice():
    assert format_rg_spice(1010.1) == "1.0101k"
    assert format_rg_spice(500) == "500.00"


def test_single_pulse_shape():
    cfg = EODPulseConfig(
        pulse_mv=2.0,
        num_pulses=1,
        start_ms=0.0,
        duration_ms=5.0,
        phase_ms=0.5,
    )
    time_s, vp, vn, _ = generate_eod_pulse_train(cfg)
    vin = vp - vn

    peak_idx = np.argmax(vin)
    trough_idx = np.argmin(vin)

    assert vin[peak_idx] == pytest.approx(2e-3, rel=1e-6)
    assert vin[trough_idx] == pytest.approx(-2e-3, rel=1e-6)
    assert vp[peak_idx] == pytest.approx(2.501, rel=1e-6)
    assert vn[peak_idx] == pytest.approx(2.499, rel=1e-6)


def test_electrode_drive_mode():
    cfg = EODPulseConfig(
        pulse_mv=2.0,
        drive_mode="electrodes",
        num_pulses=1,
        start_ms=0.0,
        duration_ms=1.0,
        sample_us=10.0,
    )
    _, vp, vn, _ = generate_eod_pulse_train(cfg)
    vin = vp - vn
    vcm = (vp + vn) / 2

    assert vin.max() == pytest.approx(2e-3, rel=1e-6)
    assert np.allclose(vcm, 0.0)
    assert vp.max() == pytest.approx(1e-3, rel=1e-6)
    assert vn.min() == pytest.approx(-1e-3, rel=1e-6)


def test_common_mode_fixed():
    cfg = EODPulseConfig(num_pulses=3)
    _, vp, vn, _ = generate_eod_pulse_train(cfg)
    vcm = (vp + vn) / 2
    assert np.allclose(vcm, cfg.vcm)


def test_write_waveform_file(tmp_path: Path):
    cfg = EODPulseConfig(duration_ms=10.0, num_pulses=2)
    result = generate_and_write_pwl(tmp_path, cfg)

    assert result.diff_path.is_file()

    lines = result.diff_path.read_text().strip().splitlines()
    data_lines = [line for line in lines if not line.startswith("#")]
    assert len(data_lines) > 0
    parts = data_lines[0].split()
    assert len(parts) == 3


def test_rounded_pulse_peak_and_width():
    cfg = EODPulseConfig(
        pulse_shape="rounded",
        pulse_mv=1.5,
        pulse_width_us=200.0,
        num_pulses=1,
        start_ms=0.0,
        duration_ms=1.0,
        sample_us=1.0,
    )
    time_s, vp, vn, _ = generate_eod_pulse_train(cfg)
    vin = vp - vn

    assert vin.max() == pytest.approx(1.5e-3, rel=1e-3)
    assert vin.min() == pytest.approx(-1.5e-3, rel=1e-3)

    threshold = 0.01 * vin.max()
    active = np.abs(vin) > threshold
    width_s = time_s[active][-1] - time_s[active][0]
    assert width_s == pytest.approx(200e-6, rel=0.05)


def test_rounded_pulse_smooth_onset():
    cfg = EODPulseConfig(
        pulse_shape="rounded",
        pulse_mv=1.0,
        pulse_width_us=200.0,
        num_pulses=1,
        start_ms=0.0,
        duration_ms=1.0,
        sample_us=1.0,
    )
    time_s, vp, vn, _ = generate_eod_pulse_train(cfg)
    vin = vp - vn

    onset_idx = np.searchsorted(time_s, 0.0)
    assert vin[onset_idx] == pytest.approx(0.0, abs=1e-9)

    square_cfg = EODPulseConfig(
        pulse_shape="square",
        pulse_mv=1.0,
        phase_ms=0.1,
        num_pulses=1,
        start_ms=0.0,
        duration_ms=1.0,
        sample_us=1.0,
    )
    _, vp_sq, vn_sq, _ = generate_eod_pulse_train(square_cfg)
    vin_sq = vp_sq - vn_sq
    assert vin_sq[onset_idx] == pytest.approx(1e-3, rel=1e-3)


def test_recorded_pulse_peak_and_asymmetry():
    cfg = EODPulseConfig(
        pulse_shape="recorded",
        pulse_mv=300.0,
        num_pulses=1,
        start_ms=0.0,
        duration_ms=2.0,
        sample_us=1.0,
    )
    _, vp, vn, _ = generate_eod_pulse_train(cfg)
    vin = vp - vn
    tpl = cfg.recorded_template()
    pos_ratio = float(np.max(tpl.shape))
    neg_ratio = float(np.min(tpl.shape))

    assert vin.max() == pytest.approx(300e-3 * pos_ratio, rel=0.01)
    assert vin.min() == pytest.approx(300e-3 * neg_ratio, rel=0.01)
    assert abs(neg_ratio) > abs(pos_ratio)
    assert cfg.pulse_duration_s() == pytest.approx(200e-6, rel=0.05)


def test_lf_offset_disabled_unchanged():
    cfg = EODPulseConfig(
        pulse_mv=2.0,
        num_pulses=1,
        start_ms=0.0,
        duration_ms=5.0,
        phase_ms=0.5,
    )
    _, vp, vn, lf = generate_eod_pulse_train(cfg)
    assert lf is None
    assert (vp - vn).max() == pytest.approx(2e-3, rel=1e-6)


def test_lf_offset_reproducible_with_seed():
    cfg = EODPulseConfig(
        lf_offset_enabled=True,
        lf_offset_amplitude_mv=50.0,
        lf_offset_seed=42,
        duration_ms=50.0,
        num_pulses=0,
        start_ms=5.0,
    )
    _, _, _, lf1 = generate_eod_pulse_train(cfg)
    _, _, _, lf2 = generate_eod_pulse_train(cfg)
    assert lf1 is not None
    assert lf2 is not None
    assert lf1.frequency_hz == pytest.approx(lf2.frequency_hz)
    assert lf1.phase_rad == pytest.approx(lf2.phase_rad)


def test_lf_offset_frequency_in_range():
    cfg = EODPulseConfig(
        lf_offset_enabled=True,
        lf_offset_center_hz=20.0,
        lf_offset_span_hz=10.0,
        lf_offset_seed=7,
        duration_ms=10.0,
        num_pulses=0,
    )
    _, _, _, lf = generate_eod_pulse_train(cfg)
    assert lf is not None
    assert 10.0 <= lf.frequency_hz <= 30.0


def test_lf_offset_electrode_cm_unchanged():
    cfg = EODPulseConfig(
        drive_mode="electrodes",
        lf_offset_enabled=True,
        lf_offset_amplitude_mv=80.0,
        lf_offset_seed=3,
        duration_ms=20.0,
        num_pulses=1,
        start_ms=0.0,
    )
    _, vp, vn, _ = generate_eod_pulse_train(cfg)
    vcm = (vp + vn) / 2
    assert np.allclose(vcm, 0.0)


def test_lf_offset_between_pulses():
    cfg = EODPulseConfig(
        pulse_mv=100.0,
        lf_offset_enabled=True,
        lf_offset_amplitude_mv=50.0,
        lf_offset_seed=99,
        num_pulses=1,
        start_ms=5.0,
        isi_ms=20.0,
        duration_ms=30.0,
        sample_us=10.0,
    )
    time_s, vp, vn, lf = generate_eod_pulse_train(cfg)
    vin = vp - vn
    assert lf is not None

    pulse_end = cfg.start_ms * 1e-3 + cfg.pulse_duration_s()
    gap_mask = time_s > pulse_end + 1e-3
    assert np.any(gap_mask)
    gap_vin = vin[gap_mask]
    assert np.max(np.abs(gap_vin)) > 1e-6
    assert np.max(np.abs(gap_vin)) <= lf.amplitude_mv * 1e-3 + 1e-9
