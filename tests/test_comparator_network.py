"""Tests for comparator output network parameters."""

from eod_sim.comparator_network import ComparatorNetworkParams, stage_has_comparator_network


def test_comparator_network_defaults():
    net = ComparatorNetworkParams()
    assert net.c_out == "2.2n"
    assert net.r_comp == "4.7k"
    assert net.r_hyst == "1Meg"


def test_comparator_to_spice_params():
    net = ComparatorNetworkParams(c_out="10n", r_comp="10k", r_hyst="500k")
    params = net.to_spice_params()
    assert params["C_OUT"] == "10n"
    assert params["R_COMP"] == "10k"
    assert params["R_HYST"] == "500k"


def test_stage_has_comparator_network():
    assert stage_has_comparator_network("02_frontend")
    assert stage_has_comparator_network("03_detector")
    assert not stage_has_comparator_network("01_passives")
