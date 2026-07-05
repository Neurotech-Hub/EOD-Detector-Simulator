"""Tests for INA input network parameters."""

from eod_sim.input_network import InputNetworkParams, stage_has_ina_gain, stage_has_input_network


def test_input_network_defaults():
    net = InputNetworkParams()
    assert net.c_couple == "4.7n"
    assert net.r_series == "100k"
    assert net.r_vref == "10Meg"
    assert net.r_diff == "1Meg"
    assert net.c_diff == "47p"
    assert net.electrode_mismatch_pct == 0.0
    assert not net.electrode_model_enabled


def test_to_spice_params():
    net = InputNetworkParams(c_couple="10n", r_series="47k")
    params = net.to_spice_params()
    assert params["C_COUPLE"] == "10n"
    assert params["R_SERIES"] == "47k"
    assert params["R_VREF"] == "10Meg"
    assert params["R_DIFF"] == "1Meg"
    assert params["C_DIFF"] == "47p"


def test_electrode_model_off_is_stiff_drive():
    params = InputNetworkParams().to_spice_params()
    assert params["R_ELEC_A"] == "1m"
    assert params["R_ELEC_B"] == "1m"


def test_electrode_mismatch_splits_rs():
    net = InputNetworkParams(electrode_mismatch_pct=20.0)
    assert net.electrode_model_enabled
    params = net.to_spice_params()
    # Rs = 15k ± m/2: 20% mismatch -> ±10% -> 16.5k / 13.5k.
    assert params["R_ELEC_A"] == "16500"
    assert params["R_ELEC_B"] == "13500"


def test_electrode_mismatch_small_value():
    r_a, r_b = InputNetworkParams(electrode_mismatch_pct=1.0).electrode_resistances()
    assert r_a == "15075"
    assert r_b == "14925"


def test_stage_has_input_network():
    assert stage_has_input_network("01_passives")
    assert stage_has_input_network("02_frontend")
    assert stage_has_input_network("03_detector")
    assert not stage_has_input_network("00_sanity_ina333")
    assert not stage_has_input_network("00_sanity_mcp6561")


def test_stage_has_ina_gain():
    assert stage_has_ina_gain("00_sanity_ina333")
    assert stage_has_ina_gain("02_frontend")
    assert stage_has_ina_gain("03_detector")
    assert not stage_has_ina_gain("01_passives")
