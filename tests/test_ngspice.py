"""Tests for ngspice netlist patching."""

from eod_sim.ngspice import patch_netlist_params


def test_patch_netlist_params_input_network():
    content = """* bench
.param C_COUPLE=4.7n
.param R_SERIES=100k
.param R_VREF=10Meg
.param R_DIFF=1Meg
.param C_DIFF=330p
.param VREF=1.65
"""
    patched = patch_netlist_params(
        content,
        {
            "C_COUPLE": "10n",
            "R_SERIES": "47k",
            "R_VREF": "5Meg",
            "R_DIFF": "2Meg",
            "C_DIFF": "100p",
        },
    )
    assert ".param C_COUPLE=10n" in patched
    assert ".param R_SERIES=47k" in patched
    assert ".param R_VREF=5Meg" in patched
    assert ".param R_DIFF=2Meg" in patched
    assert ".param C_DIFF=100p" in patched
    assert ".param VREF=1.65" in patched
