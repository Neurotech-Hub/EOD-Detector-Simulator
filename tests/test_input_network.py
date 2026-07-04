"""Tests for INA input network parameters."""

from eod_sim.input_network import InputNetworkParams, stage_has_input_network


def test_input_network_defaults():
    net = InputNetworkParams()
    assert net.c_couple == "4.7n"
    assert net.r_series == "100k"
    assert net.r_vref == "10Meg"
    assert net.r_diff == "1Meg"
    assert net.c_diff == "330p"


def test_to_spice_params():
    net = InputNetworkParams(c_couple="10n", r_series="47k")
    params = net.to_spice_params()
    assert params["C_COUPLE"] == "10n"
    assert params["R_SERIES"] == "47k"
    assert params["R_VREF"] == "10Meg"
    assert params["R_DIFF"] == "1Meg"
    assert params["C_DIFF"] == "330p"


def test_stage_has_input_network():
    assert stage_has_input_network("01_passives")
    assert stage_has_input_network("02_frontend")
    assert stage_has_input_network("03_detector")
    assert not stage_has_input_network("00_sanity_ina333")
    assert not stage_has_input_network("00_sanity_mcp6561")
