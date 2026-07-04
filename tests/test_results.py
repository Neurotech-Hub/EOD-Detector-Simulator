"""Tests for simulation result parsing."""

import numpy as np
import pytest

from eod_sim.results import SimulationResult


def test_simulation_result_diff_pair():
    time_s = np.linspace(0, 1e-3, 101)
    result = SimulationResult(
        time_s=time_s,
        in_p=np.full(101, 1.65),
        in_n=np.full(101, 1.64),
        out=np.full(101, 1.66),
        ref=np.full(101, 1.65),
        extra={"elec_a": np.sin(2 * np.pi * 1e3 * time_s) * 1e-3},
        signal_nodes={
            "in_p": "ina_p",
            "in_n": "ina_n",
            "out": "elec_out",
            "ref": "vref",
            "elec_a": "elec_a",
        },
    )

    assert result.vin_diff[0] == pytest.approx(0.01)
    assert result.node_voltage("elec_a")[50] == result.extra["elec_a"][50]
    assert result.diff_pair("ina_p", "ina_n")[0] == pytest.approx(0.01)
