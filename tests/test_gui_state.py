"""Tests for GUI state and kHz conversion."""

import pytest

from eod_sim.gui.state import GuiState, parse_float, parse_int, stage_supports_tab
from eod_sim.waveforms import isi_ms_from_khz, pulse_rate_khz


def test_khz_isi_round_trip():
    assert isi_ms_from_khz(0.5) == pytest.approx(2.0)
    assert pulse_rate_khz(2.0) == pytest.approx(0.5)
    assert pulse_rate_khz(isi_ms_from_khz(1.0)) == pytest.approx(1.0)


def test_khz_invalid():
    with pytest.raises(ValueError):
        isi_ms_from_khz(0)


def test_gui_state_to_run_config():
    state = GuiState(pulse_rate_khz=0.5, stage_id="03_detector")
    cfg = state.to_run_config()
    assert cfg.isi_ms == pytest.approx(2.0)
    assert cfg.stage_id == "03_detector"
    assert cfg.pulse_zoom is False


def test_gui_state_lf_offset_mapping():
    state = GuiState(
        lf_offset_enabled=True,
        lf_offset_amplitude_mv=150.0,
        lf_offset_center_hz=20.0,
        lf_offset_span_hz=10.0,
        lf_offset_seed=12,
    )
    cfg = state.to_run_config()
    assert cfg.lf_offset_enabled is True
    assert cfg.lf_offset_amplitude_mv == pytest.approx(150.0)
    assert cfg.lf_offset_seed == 12


def test_gui_state_input_network_mapping():
    state = GuiState(
        c_couple="10n",
        r_series="47k",
        r_vref="5Meg",
        r_diff="2Meg",
        c_diff="100p",
    )
    cfg = state.to_run_config()
    assert cfg.input_network is not None
    assert cfg.input_network.c_couple == "10n"
    assert cfg.input_network.r_series == "47k"
    assert cfg.input_network.r_vref == "5Meg"
    assert cfg.input_network.r_diff == "2Meg"
    assert cfg.input_network.c_diff == "100p"


def test_stage_supports_tab():
    assert stage_supports_tab("02_frontend", 1)
    assert stage_supports_tab("02_frontend", 2)
    assert not stage_supports_tab("02_frontend", 3)
    assert stage_supports_tab("03_detector", 3)
    assert not stage_supports_tab("01_passives", 1)


def test_parse_float_and_int():
    assert parse_float("0.5", 1.0) == pytest.approx(0.5)
    assert parse_float(2, 1.0) == pytest.approx(2.0)
    assert parse_float("", 3.0) == pytest.approx(3.0)
    assert parse_float(None, 4.0) == pytest.approx(4.0)
    assert parse_int("4", 1) == 4
    assert parse_int("", 2) == 2
