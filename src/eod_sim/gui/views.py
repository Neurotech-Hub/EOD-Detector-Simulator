"""Plotly figure builders for the tuning GUI."""

from __future__ import annotations

from typing import Literal

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from eod_sim.gui.state import GuiState, stage_supports_tab
from eod_sim.results import SimulationResult
from eod_sim.waveforms import EODPulseConfig

ViewMode = Literal["overview", "pulse"]

_COL_INPUT = "#2563eb"
_COL_ELEC_OUT = "#dc2626"
_COL_COMP_IN = "#dc2626"
_COL_THRESH = "#f59e0b"
_COL_TRIGGER = "#16a34a"


def _time_axis_ms(result: SimulationResult, state: GuiState) -> np.ndarray:
    if state.view_mode == "overview":
        return result.time_s * 1e3
    cfg = _pulse_config(state)
    t_start, t_end = cfg.pulse_view_window_s(
        pulse_index=state.pulse_index,
        window_scale=state.pulse_window_scale,
    )
    mask = (result.time_s >= t_start) & (result.time_s <= t_end)
    t0 = cfg.pulse_onset_s(state.pulse_index)
    return (result.time_s[mask] - t0) * 1e6


def _mask(result: SimulationResult, state: GuiState) -> np.ndarray:
    if state.view_mode == "overview":
        return np.ones_like(result.time_s, dtype=bool)
    cfg = _pulse_config(state)
    t_start, t_end = cfg.pulse_view_window_s(
        pulse_index=state.pulse_index,
        window_scale=state.pulse_window_scale,
    )
    return (result.time_s >= t_start) & (result.time_s <= t_end)


def _pulse_config(state: GuiState) -> EODPulseConfig:
    stage = state.stage()
    return EODPulseConfig(
        pulse_mv=state.pulse_mv,
        pulse_shape=state.pulse_shape,
        pulse_width_us=state.pulse_width_us,
        isi_ms=state.isi_ms(),
        num_pulses=state.num_pulses,
        duration_ms=state.duration_ms,
        start_ms=state.start_ms,
        drive_mode=stage.drive_mode,
        vcm=stage.default_vcm,
    )


def _electrode_diff_mv(result: SimulationResult, mask: np.ndarray) -> np.ndarray:
    return result.diff_pair("elec_a", "elec_b")[mask] * 1e3


def _has_node(result: SimulationResult, node: str) -> bool:
    try:
        result.node_voltage(node)
        return True
    except KeyError:
        return False


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(margin=dict(l=40, r=40, t=40, b=40))
    return fig


def _x_label(state: GuiState) -> str:
    return "Time (ms)" if state.view_mode == "overview" else "Time from pulse onset (µs)"


def build_input_elec_out_figure(
    result: SimulationResult | None,
    state: GuiState,
) -> go.Figure:
    if result is None:
        return _empty_figure("Run a simulation to view plots.")
    if not stage_supports_tab(state.stage_id, 1):
        return _empty_figure("Input vs ELEC_OUT requires stage 02_frontend or 03_detector.")
    if not _has_node(result, "elec_out"):
        return _empty_figure("ELEC_OUT not available in this simulation.")

    mask = _mask(result, state)
    t = _time_axis_ms(result, state)
    vin = _electrode_diff_mv(result, mask)
    elec_out = result.node_voltage("elec_out")[mask]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=t, y=vin, name="Input (ELEC_A − ELEC_B)", line=dict(color=_COL_INPUT)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=t, y=elec_out, name="ELEC_OUT", line=dict(color=_COL_ELEC_OUT)),
        secondary_y=True,
    )
    fig.update_xaxes(title_text=_x_label(state))
    fig.update_yaxes(title_text="Input (mV)", secondary_y=False, color=_COL_INPUT)
    fig.update_yaxes(title_text="ELEC_OUT (V)", secondary_y=True, color=_COL_ELEC_OUT)
    fig.update_layout(
        title="Input vs ELEC_OUT",
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=60, r=60, t=50, b=50),
    )
    return fig


def build_input_comp_in_figure(
    result: SimulationResult | None,
    state: GuiState,
) -> go.Figure:
    if result is None:
        return _empty_figure("Run a simulation to view plots.")
    if not stage_supports_tab(state.stage_id, 2):
        return _empty_figure("Input vs COMP_IN requires stage 02_frontend or 03_detector.")
    if not _has_node(result, "comp_in"):
        return _empty_figure("COMP_IN not available in this simulation.")

    mask = _mask(result, state)
    t = _time_axis_ms(result, state)
    vin = _electrode_diff_mv(result, mask)
    comp_in = result.node_voltage("comp_in")[mask]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=t, y=vin, name="Input (ELEC_A − ELEC_B)", line=dict(color=_COL_INPUT)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=t, y=comp_in, name="COMP_IN", line=dict(color=_COL_COMP_IN)),
        secondary_y=True,
    )
    fig.update_xaxes(title_text=_x_label(state))
    fig.update_yaxes(title_text="Input (mV)", secondary_y=False, color=_COL_INPUT)
    fig.update_yaxes(title_text="COMP_IN (V)", secondary_y=True, color=_COL_COMP_IN)
    fig.update_layout(
        title="Input vs COMP_IN",
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=60, r=60, t=50, b=50),
    )
    return fig


def build_comparator_figure(
    result: SimulationResult | None,
    state: GuiState,
) -> go.Figure:
    if result is None:
        return _empty_figure("Run a simulation to view plots.")
    if not stage_supports_tab(state.stage_id, 3):
        return _empty_figure("Comparator view requires stage 03_detector.")
    if not _has_node(result, "comp_out"):
        return _empty_figure("Comparator output not available in this simulation.")

    mask = _mask(result, state)
    t = _time_axis_ms(result, state)
    comp_in = result.node_voltage("comp_in")[mask]
    thresh = result.node_voltage("thresh")[mask]
    trigger = result.node_voltage("comp_out")[mask]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(x=t, y=comp_in, name="COMP_IN", line=dict(color=_COL_COMP_IN)),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=t, y=thresh, name="THRESH", line=dict(color=_COL_THRESH, dash="dash")),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=t, y=trigger, name="TRIGGER", line=dict(color=_COL_TRIGGER)),
        secondary_y=True,
    )
    fig.update_xaxes(title_text=_x_label(state))
    fig.update_yaxes(title_text="COMP_IN / THRESH (V)", secondary_y=False)
    fig.update_yaxes(title_text="TRIGGER (V)", secondary_y=True, color=_COL_TRIGGER)
    fig.update_layout(
        title="COMP_IN + THRESH vs TRIGGER",
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=60, r=60, t=50, b=50),
    )
    return fig


def build_all_figures(
    result: SimulationResult | None,
    state: GuiState,
) -> tuple[go.Figure, go.Figure, go.Figure]:
    return (
        build_input_elec_out_figure(result, state),
        build_input_comp_in_figure(result, state),
        build_comparator_figure(result, state),
    )
