"""Tests for GUI Plotly view builders."""

import numpy as np

from eod_sim.gui.state import GuiState
from eod_sim.gui.views import (
    build_comparator_figure,
    build_input_comp_in_figure,
    build_input_elec_out_figure,
)
from eod_sim.results import SimulationResult


def _synthetic_result() -> SimulationResult:
    time_s = np.linspace(0, 0.1, 1001)
    elec_a = 0.5e-3 * np.sin(2 * np.pi * 500 * time_s)
    elec_b = -elec_a
    return SimulationResult(
        time_s=time_s,
        in_p=np.full(1001, 1.65),
        in_n=np.full(1001, 1.64),
        out=1.65 + 2e-3 * np.sin(2 * np.pi * 500 * time_s),
        ref=np.full(1001, 1.65),
        extra={
            "elec_a": elec_a,
            "elec_b": elec_b,
            "elec_out": 1.65 + 2e-3 * np.sin(2 * np.pi * 500 * time_s),
            "comp_in": 1.65 + 1.5e-3 * np.sin(2 * np.pi * 500 * time_s),
            "comp_out": np.where(np.sin(2 * np.pi * 500 * time_s) > 0, 3.3, 0.0),
            "thresh": np.full(1001, 1.85),
        },
        signal_nodes={
            "in_p": "ina_p",
            "in_n": "ina_n",
            "out": "comp_out",
            "ref": "vref",
            "elec_out": "elec_out",
        },
    )


def test_build_input_elec_out_figure():
    state = GuiState(stage_id="02_frontend", view_mode="overview")
    fig = build_input_elec_out_figure(_synthetic_result(), state)
    assert len(fig.data) == 2
    assert "ELEC_OUT" in fig.data[1].name


def test_build_input_comp_in_figure():
    state = GuiState(stage_id="02_frontend", view_mode="overview")
    fig = build_input_comp_in_figure(_synthetic_result(), state)
    assert len(fig.data) == 2
    assert fig.data[1].name == "COMP_IN"


def test_build_comparator_figure():
    state = GuiState(stage_id="03_detector", view_mode="overview")
    fig = build_comparator_figure(_synthetic_result(), state)
    assert len(fig.data) == 3
    names = {trace.name for trace in fig.data}
    assert names == {"COMP_IN", "THRESH", "TRIGGER"}


def test_unavailable_stage_shows_message():
    state = GuiState(stage_id="01_passives")
    fig = build_input_elec_out_figure(_synthetic_result(), state)
    assert fig.data == ()
