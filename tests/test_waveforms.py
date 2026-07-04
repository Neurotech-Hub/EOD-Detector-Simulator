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
    time_s, vp, vn = generate_eod_pulse_train(cfg)
    vin = vp - vn

    peak_idx = np.argmax(vin)
    trough_idx = np.argmin(vin)

    assert vin[peak_idx] == pytest.approx(2e-3, rel=1e-6)
    assert vin[trough_idx] == pytest.approx(-2e-3, rel=1e-6)
    assert vp[peak_idx] == pytest.approx(2.501, rel=1e-6)
    assert vn[peak_idx] == pytest.approx(2.499, rel=1e-6)


def test_common_mode_fixed():
    cfg = EODPulseConfig(num_pulses=3)
    _, vp, vn = generate_eod_pulse_train(cfg)
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
