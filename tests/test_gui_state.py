"""Tests for GUI state and kHz conversion."""

import pytest

from eod_sim.gui.state import (
    GuiState,
    default_ina_gain,
    parse_float,
    parse_ina_gain,
    parse_int,
    resolve_gui_gain,
    stage_supports_tab,
)
from eod_sim.waveforms import isi_ms_from_khz, pulse_rate_khz


def test_khz_isi_round_trip():
    assert isi_ms_from_khz(0.5) == pytest.approx(2.0)
    assert pulse_rate_khz(2.0) == pytest.approx(0.5)
    assert pulse_rate_khz(isi_ms_from_khz(1.0)) == pytest.approx(1.0)


def test_khz_invalid():
    with pytest.raises(ValueError):
        isi_ms_from_khz(0)


def test_gui_state_to_run_config():
    state = GuiState(pulse_rate_khz=0.5, stage_id="03_detector", gain=5.0)
    cfg = state.to_run_config()
    assert cfg.isi_ms == pytest.approx(2.0)
    assert cfg.stage_id == "03_detector"
    assert cfg.gain == pytest.approx(5.0)
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


def test_gui_state_comparator_network_mapping():
    state = GuiState(c_out="10n", r_comp="10k", r_hyst="500k")
    cfg = state.to_run_config()
    assert cfg.comparator_network is not None
    assert cfg.comparator_network.c_out == "10n"
    assert cfg.comparator_network.r_comp == "10k"
    assert cfg.comparator_network.r_hyst == "500k"


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


def test_default_ina_gain():
    assert default_ina_gain("00_sanity_ina333") == pytest.approx(100.0)
    assert default_ina_gain("02_frontend") == pytest.approx(2.0)
    assert default_ina_gain("03_detector") == pytest.approx(2.0)


def test_parse_ina_gain():
    assert parse_ina_gain("5", 2) == pytest.approx(5.0)
    assert parse_ina_gain("1", 2) == pytest.approx(2.0)
    assert parse_ina_gain("", 2) == pytest.approx(2.0)


def test_resolve_gui_gain():
    assert resolve_gui_gain("00_sanity_ina333", "2", "50") == pytest.approx(50.0)
    assert resolve_gui_gain("02_frontend", "10", "100") == pytest.approx(10.0)
    assert resolve_gui_gain("03_detector", "3", "100") == pytest.approx(3.0)
    assert resolve_gui_gain("01_passives", "10", "100") == pytest.approx(2.0)
