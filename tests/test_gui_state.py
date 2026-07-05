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
    assert cfg.input_network.electrode_mismatch_pct == 0.0


def test_gui_state_electrode_mismatch_round_trip():
    state = GuiState(electrode_mismatch_pct=20.0)
    restored = GuiState.from_dict(state.to_dict())
    assert restored.electrode_mismatch_pct == 20.0
    cfg = restored.to_run_config()
    assert cfg.input_network.electrode_mismatch_pct == 20.0
    params = cfg.input_network.to_spice_params()
    assert params["R_ELEC_A"] == "16500"
    assert params["R_ELEC_B"] == "13500"


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
    assert default_ina_gain("02_frontend") == pytest.approx(3.0)
    assert default_ina_gain("03_detector") == pytest.approx(3.0)


def test_gui_state_recommended_defaults():
    state = GuiState()
    assert state.gain == pytest.approx(3.0)
    assert state.c_diff == "47p"
    assert state.c_out == "470p"


def test_r3_display_for_gain():
    from eod_sim.gui.state import r3_display_for_gain

    assert r3_display_for_gain(3.0) == "50.0000k"
    assert r3_display_for_gain(2.0) == "100.0000k"


def test_format_settings_report():
    from eod_sim.gui.state import format_settings_report, get_component_defaults

    text = format_settings_report(GuiState())
    assert "03_detector" in text
    assert "component defaults: Ideal v3" in text
    assert "C4=47p" in text
    assert "C5=470p" in text
    assert "gain: 3 V/V" in text
    assert "R3 (RG) = 50.0000k" in text


def test_component_defaults_presets():
    from eod_sim.gui.state import NO_C4_DIFF, get_component_defaults

    stock = get_component_defaults("detector_v3")
    assert stock.label == "Detector v3"
    assert stock.gain == pytest.approx(2.0)
    assert stock.c_diff == "330p"
    assert stock.c_out == "2.2n"

    no_c4 = get_component_defaults("detector_v3_no_c4")
    assert no_c4.label == "Detector v3 - No C4"
    assert no_c4.gain == pytest.approx(2.0)
    assert no_c4.c_diff == NO_C4_DIFF
    assert no_c4.c_out == "2.2n"

    ideal = get_component_defaults("ideal_v3")
    assert ideal.label == "Ideal v3"
    assert ideal.gain == pytest.approx(3.0)
    assert ideal.c_diff == "47p"
    assert ideal.c_out == "470p"


def test_parse_ina_gain():
    assert parse_ina_gain("5", 2) == pytest.approx(5.0)
    assert parse_ina_gain("1", 2) == pytest.approx(2.0)
    assert parse_ina_gain("", 2) == pytest.approx(2.0)


def test_resolve_gui_gain():
    assert resolve_gui_gain("00_sanity_ina333", "2", "50") == pytest.approx(50.0)
    assert resolve_gui_gain("02_frontend", "10", "100") == pytest.approx(10.0)
    assert resolve_gui_gain("03_detector", "3", "100") == pytest.approx(3.0)
    assert resolve_gui_gain("01_passives", "10", "100") == pytest.approx(2.0)
