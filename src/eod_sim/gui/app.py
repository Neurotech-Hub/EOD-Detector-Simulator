"""Plotly Dash application for EOD detector tuning."""

from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path

from dash import Dash, Input, Output, State, callback, dcc, html, no_update

from eod_sim.gui.state import (
    GuiState,
    RECOMMENDED_C_DIFF,
    RECOMMENDED_C_OUT,
    RECOMMENDED_GAIN,
    COMPONENT_DEFAULTS,
    default_ina_gain,
    format_settings_report,
    get_component_defaults,
    parse_float,
    parse_int,
    parse_ina_gain,
    parse_optional_int,
    parse_spice_value,
    r3_display_for_gain,
    resolve_gui_gain,
)
from eod_sim.gui.views import _empty_figure, build_all_figures
from eod_sim.comparator_network import stage_has_comparator_network
from eod_sim.input_network import stage_has_input_network
from eod_sim.ngspice import NgspiceNotFoundError, NgspiceSimulationError
from eod_sim.results import SimulationResult, load_raw
from eod_sim.runner import run_simulation
from eod_sim.stages.registry import get_stage, list_stages
from eod_sim.validation import SimulationValidationError
from eod_sim.waveforms import LFOffsetParams

_INPUT_STYLE = {"width": "100%", "boxSizing": "border-box", "fontSize": "13px"}
_DISABLED_INPUT_STYLE = {
    **_INPUT_STYLE,
    "backgroundColor": "#f3f4f6",
    "color": "#555",
    "cursor": "default",
}
_LABEL_STYLE = {"fontSize": "13px", "color": "#333", "alignSelf": "center"}
_HINT_STYLE = {
    "fontSize": "11px",
    "color": "#666",
    "margin": "2px 0 0 0",
    "gridColumn": "1 / -1",
}
_CARD_STYLE = {
    "border": "1px solid #e5e7eb",
    "borderRadius": "6px",
    "padding": "10px 12px",
    "marginBottom": "12px",
}
_CARD_TITLE_STYLE = {
    "fontSize": "11px",
    "fontWeight": "600",
    "textTransform": "uppercase",
    "letterSpacing": "0.05em",
    "color": "#555",
    "margin": "0 0 8px 0",
}


def _runnable_stages():
    return [s for s in list_stages() if s.is_runnable]


def _stage_options():
    return [{"label": f"{s.id} — {s.title}", "value": s.id} for s in _runnable_stages()]


def _bench_options(stage_id: str):
    stage = get_stage(stage_id)
    return [{"label": v, "value": v} for v in stage.benches]


def _decimal_input(component_id: str, value: float | int) -> dcc.Input:
    """Text input with debounce — avoids broken browser number spinners."""
    return dcc.Input(
        id=component_id,
        type="text",
        inputMode="decimal",
        value=str(value),
        debounce=True,
        style=_INPUT_STYLE,
    )


def _spice_input(component_id: str, value: str) -> dcc.Input:
    """Text input for SPICE component literals (e.g. 4.7n, 100k)."""
    return dcc.Input(
        id=component_id,
        type="text",
        value=value,
        debounce=True,
        style=_INPUT_STYLE,
    )


def _disabled_input(component_id: str, value: str) -> dcc.Input:
    """Read-only display matching editable inputs."""
    return dcc.Input(
        id=component_id,
        type="text",
        value=value,
        readOnly=True,
        disabled=True,
        style=_DISABLED_INPUT_STYLE,
    )


def _load_result(raw_path: str | None, stage_id: str) -> SimulationResult | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.is_file():
        return None
    stage = get_stage(stage_id)
    return load_raw(
        path,
        signal_nodes=stage.resolved_signal_nodes() if stage.signal_nodes else None,
        extra_probes=stage.extra_probes,
    )


def _gui_state_from_inputs(
    stage_id,
    bench_variant,
    component_defaults,
    pulse_rate_khz,
    pulse_mv,
    pulse_shape,
    pulse_width_us,
    num_pulses,
    duration_ms,
    lf_offset_enabled,
    lf_offset_mv,
    lf_offset_center_hz,
    lf_offset_span_hz,
    lf_offset_seed,
    c_couple,
    r_series,
    r_vref,
    r_diff,
    c_diff,
    electrode_mismatch,
    c_out,
    r_comp,
    r_hyst,
    vref,
    vthresh,
    vdd,
    ina_gain,
    sanity_gain,
    view_mode,
) -> GuiState:
    enabled = bool(lf_offset_enabled) and "enabled" in (lf_offset_enabled or [])
    stage = get_stage(stage_id or "03_detector")
    preset_id = component_defaults if component_defaults in COMPONENT_DEFAULTS else "ideal_v3"
    return GuiState(
        stage_id=stage_id or "03_detector",
        bench_variant=bench_variant or stage.default_bench,
        component_defaults=preset_id,
        pulse_rate_khz=parse_float(pulse_rate_khz, 0.5),
        pulse_mv=parse_float(pulse_mv, 300.0),
        pulse_shape=pulse_shape or "rounded",
        pulse_width_us=parse_float(pulse_width_us, 200.0),
        num_pulses=parse_int(num_pulses, 4),
        duration_ms=parse_float(duration_ms, 20.0),
        lf_offset_enabled=enabled,
        lf_offset_amplitude_mv=parse_float(lf_offset_mv, 100.0),
        lf_offset_center_hz=parse_float(lf_offset_center_hz, 20.0),
        lf_offset_span_hz=parse_float(lf_offset_span_hz, 10.0),
        lf_offset_seed=parse_optional_int(lf_offset_seed),
        c_couple=parse_spice_value(c_couple, "4.7n"),
        r_series=parse_spice_value(r_series, "100k"),
        r_vref=parse_spice_value(r_vref, "10Meg"),
        r_diff=parse_spice_value(r_diff, "1Meg"),
        c_diff=parse_spice_value(c_diff, RECOMMENDED_C_DIFF),
        electrode_mismatch_pct=max(parse_float(electrode_mismatch, 0.0), 0.0),
        c_out=parse_spice_value(c_out, RECOMMENDED_C_OUT),
        r_comp=parse_spice_value(r_comp, "4.7k"),
        r_hyst=parse_spice_value(r_hyst, "1Meg"),
        vref=parse_float(vref, 1.65),
        vthresh=parse_float(vthresh, 1.85),
        vdd=parse_float(vdd, 3.3),
        gain=resolve_gui_gain(stage_id, ina_gain, sanity_gain),
        view_mode=view_mode or "pulse",
    )


def _state_for_plot(result_data: dict | None, live_state: GuiState) -> GuiState:
    """Use simulation params from last run; keep live view controls."""
    if result_data and result_data.get("sim_state"):
        sim = GuiState.from_dict(result_data["sim_state"])
        sim.view_mode = live_state.view_mode
        return sim
    return live_state


def _field(label: str, control, hint: str | None = None) -> html.Div:
    """Compact label/input row: label left, control right, optional hint below."""
    children = [html.Label(label, style=_LABEL_STYLE), control]
    if hint:
        children.append(html.P(hint, style=_HINT_STYLE))
    return html.Div(
        style={
            "display": "grid",
            "gridTemplateColumns": "1.2fr 1fr",
            "columnGap": "8px",
            "alignItems": "center",
            "marginBottom": "6px",
        },
        children=children,
    )


def _card(title: str, *children) -> html.Div:
    """Bordered, always-open section card with an uppercase heading."""
    return html.Div(
        style=_CARD_STYLE,
        children=[html.Div(title, style=_CARD_TITLE_STYLE), *children],
    )


def _note(text: str) -> html.P:
    return html.P(text, style={"fontSize": "11px", "color": "#666", "margin": "0 0 6px 0"})


def _control_block() -> html.Div:
    default_stage = get_stage("03_detector")

    stage_bench_card = _card(
        "Stage & Bench",
        html.Label("Stage", style=_LABEL_STYLE),
        dcc.Dropdown(
            id="stage-select",
            options=_stage_options(),
            value="03_detector",
            style={"marginBottom": "6px"},
        ),
        html.Label("Bench", style=_LABEL_STYLE),
        dcc.Dropdown(
            id="bench-select",
            options=_bench_options("03_detector"),
            value=default_stage.default_bench,
            style={"marginBottom": "6px"},
        ),
        html.Label("Component defaults", style=_LABEL_STYLE),
        dcc.Dropdown(
            id="component-defaults",
            options=[
                {"label": "Detector v3", "value": "detector_v3"},
                {"label": "Detector v3 - No C4", "value": "detector_v3_no_c4"},
                {"label": "Ideal v3", "value": "ideal_v3"},
            ],
            value="ideal_v3",
            clearable=False,
        ),
    )

    waveform_card = _card(
        "Waveform",
        _field("Pulse rate (kHz)", _decimal_input("pulse-rate-khz", 0.5)),
        _field("Pulse amplitude (mV)", _decimal_input("pulse-mv", 300)),
        _field(
            "Pulse shape",
            dcc.Dropdown(
                id="pulse-shape",
                options=[
                    {"label": "Rounded", "value": "rounded"},
                    {"label": "Square", "value": "square"},
                ],
                value="rounded",
                clearable=False,
            ),
        ),
        _field("Pulse width (µs)", _decimal_input("pulse-width-us", 200)),
        _field("Num pulses", _decimal_input("num-pulses", 4)),
        _field("Duration (ms)", _decimal_input("duration-ms", 20)),
    )

    lf_offset_card = _card(
        "Slow water offset",
        dcc.Checklist(
            id="lf-offset-enabled",
            options=[{"label": " Slow water offset (~20 Hz)", "value": "enabled"}],
            value=[],
            style={"marginBottom": "6px", "fontSize": "13px"},
        ),
        html.Div(
            id="lf-offset-controls",
            style={"display": "none"},
            children=[
                _field("LF offset amplitude (mV)", _decimal_input("lf-offset-mv", 100)),
                _field("LF center frequency (Hz)", _decimal_input("lf-offset-center-hz", 20)),
                _field("LF frequency span ± (Hz)", _decimal_input("lf-offset-span-hz", 10)),
                _field(
                    "LF seed (optional)",
                    dcc.Input(
                        id="lf-offset-seed",
                        type="text",
                        inputMode="numeric",
                        placeholder="random each run",
                        debounce=True,
                        style=_INPUT_STYLE,
                    ),
                    hint="Each run draws f in [center−span, center+span] and a random phase vs first pulse.",
                ),
            ],
        ),
    )

    voltages_card = _card(
        "Circuit voltages",
        _field("VREF (V)", _decimal_input("vref", 1.65)),
        _field(
            "VTHRESH (V)",
            _decimal_input("vthresh", 1.85),
            hint="On the board this is the RV1 trimmer wiper (R13/R17 divider).",
        ),
        _field("VDD (V)", _decimal_input("vdd", 3.3)),
        html.Div(
            id="gain-control",
            style={"display": "none"},
            children=[
                _field("INA333 gain (V/V)", _decimal_input("sanity-gain", 100)),
                _field(
                    "R3 (RG)",
                    _disabled_input("sanity-r3", r3_display_for_gain(100.0)),
                    hint="Read-only; set by gain above.",
                ),
            ],
        ),
    )

    input_network_panel = html.Div(
        id="input-network-panel",
        children=[
            _card(
                "INA input network",
                html.Div(
                    id="ina-gain-control",
                    style={"display": "none"},
                    children=[
                        _field(
                            "INA333 gain (V/V)",
                            _decimal_input("ina-gain", int(RECOMMENDED_GAIN)),
                            hint="Sets R3 (RG); G = 1 + 100k/RG. Minimum 2 V/V.",
                        ),
                        _field(
                            "R3 (RG)",
                            _disabled_input(
                                "ina-r3", r3_display_for_gain(RECOMMENDED_GAIN)
                            ),
                            hint="Read-only; patched into the netlist from gain.",
                        ),
                    ],
                ),
                _note("Symmetric per-leg values; SPICE units (n, k, Meg, p)."),
                _field("Input coupling cap (C2/C3)", _spice_input("c-couple", "4.7n")),
                _field("Series input resistor (R4/R7)", _spice_input("r-series", "100k")),
                _field("VREF bias resistor (R6/R8)", _spice_input("r-vref", "10Meg")),
                _field("Differential input resistor (R15)", _spice_input("r-diff", "1Meg")),
                _field("Differential input capacitor (C4)", _spice_input("c-diff", RECOMMENDED_C_DIFF)),
                _field(
                    "Electrode mismatch (%)",
                    _decimal_input("electrode-mismatch", 0),
                    hint=(
                        "0 = ideal stiff drive; >0 inserts Rs = 15 kΩ ± m/2 "
                        "per electrode — see ELECTRODES.md."
                    ),
                ),
            ),
        ],
    )

    comparator_panel = html.Div(
        id="comparator-network-panel",
        children=[
            _card(
                "Comparator network",
                _note("Output coupling and hysteresis; SPICE units (n, k, Meg)."),
                _field("Output coupling cap (C5, VREF–ELEC_OUT)", _spice_input("c-out", RECOMMENDED_C_OUT)),
                _field("COMP_IN series resistor (R9)", _spice_input("r-comp", "4.7k")),
                html.Div(
                    id="r-hyst-control",
                    children=[
                        _field(
                            "Hysteresis resistor (R5, COMP_IN–TRIGGER)",
                            _spice_input("r-hyst", "1Meg"),
                        ),
                    ],
                ),
            ),
        ],
    )

    view_card = _card(
        "View",
        dcc.RadioItems(
            id="view-mode",
            options=[
                {"label": " Overview ", "value": "overview"},
                {"label": " Single pulse ", "value": "pulse"},
            ],
            value="pulse",
            inline=True,
            style={"fontSize": "13px"},
        ),
        html.P(
            "Single pulse: first pulse in the train; x-axis spans 2× pulse width.",
            style={"fontSize": "11px", "color": "#666", "margin": "4px 0 0 0"},
        ),
    )

    # Left column = signal, right column = circuit.
    left_column = html.Div(children=[stage_bench_card, waveform_card, lf_offset_card, view_card])
    right_column = html.Div(
        children=[voltages_card, input_network_panel, comparator_panel]
    )

    return html.Div(
        id="sidebar",
        style={
            "width": "620px",
            "flexShrink": 0,
            "display": "flex",
            "flexDirection": "column",
            "borderRight": "1px solid #ddd",
            "minHeight": 0,
        },
        children=[
            html.Div(
                style={
                    "flex": 1,
                    "overflowY": "auto",
                    "padding": "12px 16px",
                    "display": "grid",
                    "gridTemplateColumns": "1fr 1fr",
                    "columnGap": "16px",
                    "alignContent": "start",
                },
                children=[left_column, right_column],
            ),
            html.Div(
                style={
                    "padding": "10px 16px",
                    "borderTop": "1px solid #ddd",
                    "background": "#fafafa",
                },
                children=[
                    html.Button(
                        "Run Simulation", id="run-button", n_clicks=0, style={"width": "100%"}
                    ),
                    dcc.Loading(
                        type="dot",
                        children=html.Div(
                            id="status-line",
                            style={"marginTop": "8px", "fontSize": "13px", "color": "#444"},
                        ),
                    ),
                    html.Div(
                        id="metrics-line",
                        style={"marginTop": "6px", "fontSize": "12px", "color": "#333"},
                    ),
                    html.Div(
                        id="stage-mismatch-line",
                        style={"marginTop": "6px", "fontSize": "12px", "color": "#b45309"},
                    ),
                    html.Div(
                        id="settings-report",
                        n_clicks=0,
                        title="Click to copy settings report",
                        style={
                            "marginTop": "8px",
                            "padding": "8px",
                            "background": "#fff",
                            "border": "1px solid #e5e7eb",
                            "borderRadius": "4px",
                            "cursor": "pointer",
                            "fontSize": "11px",
                            "fontFamily": "ui-monospace, SFMono-Regular, Menlo, monospace",
                            "whiteSpace": "pre-wrap",
                            "color": "#374151",
                            "lineHeight": "1.45",
                        },
                        children=[
                            html.Div(
                                "Settings report — click to copy",
                                style={
                                    "fontSize": "10px",
                                    "color": "#888",
                                    "marginBottom": "4px",
                                    "fontFamily": "system-ui, sans-serif",
                                },
                            ),
                            html.Pre(
                                id="settings-report-pre",
                                style={
                                    "margin": 0,
                                    "fontSize": "inherit",
                                    "fontFamily": "inherit",
                                    "whiteSpace": "pre-wrap",
                                },
                            ),
                        ],
                    ),
                    html.Span(
                        id="copy-feedback",
                        style={
                            "fontSize": "11px",
                            "color": "#059669",
                            "marginTop": "4px",
                            "display": "block",
                            "minHeight": "14px",
                        },
                    ),
                    dcc.Store(id="settings-report-text"),
                ],
            ),
        ],
    )


def create_app(project_root: Path) -> Dash:
    app = Dash(__name__, suppress_callback_exceptions=True)
    app.title = "EOD Detector Tuner"

    app.layout = html.Div(
        style={"fontFamily": "system-ui, sans-serif", "height": "100vh", "display": "flex", "flexDirection": "column"},
        children=[
            html.Div(
                style={"padding": "12px 16px", "borderBottom": "1px solid #ddd"},
                children=[html.H2("EOD Detector Tuner", style={"margin": 0})],
            ),
            html.Div(
                style={"display": "flex", "flex": 1, "minHeight": 0},
                children=[
                    _control_block(),
                    html.Div(
                        style={"flex": 1, "padding": "12px", "overflow": "auto"},
                        children=[
                            dcc.Tabs(
                                id="plot-tabs",
                                value="tab-1",
                                children=[
                                    dcc.Tab(label="Electrodes vs ELEC_OUT", value="tab-1"),
                                    dcc.Tab(label="ELEC_OUT vs COMP_IN", value="tab-2"),
                                    dcc.Tab(label="Comparator", value="tab-3"),
                                ],
                            ),
                            dcc.Loading(
                                type="default",
                                children=dcc.Graph(
                                    id="main-plot", style={"height": "calc(100vh - 140px)"}
                                ),
                            ),
                        ],
                    ),
                ],
            ),
            dcc.Store(id="result-store"),
            html.Div(id="project-root", style={"display": "none"}, children=str(project_root)),
        ],
    )

    @callback(
        Output("lf-offset-controls", "style"),
        Input("lf-offset-enabled", "value"),
    )
    def toggle_lf_offset_controls(enabled):
        if enabled and "enabled" in enabled:
            return {"display": "block"}
        return {"display": "none"}

    @callback(
        Output("input-network-panel", "style"),
        Input("stage-select", "value"),
    )
    def toggle_input_network_panel(stage_id):
        if stage_id and stage_has_input_network(stage_id):
            return {"display": "block"}
        return {"display": "none"}

    @callback(
        Output("comparator-network-panel", "style"),
        Input("stage-select", "value"),
    )
    def toggle_comparator_network_panel(stage_id):
        if stage_id and stage_has_comparator_network(stage_id):
            return {"display": "block"}
        return {"display": "none"}

    @callback(
        Output("r-hyst-control", "style"),
        Input("stage-select", "value"),
    )
    def toggle_comparator_only_controls(stage_id):
        # R5 only exists when the comparator is populated (stage 03).
        return {"display": "block"} if stage_id == "03_detector" else {"display": "none"}

    @callback(
        Output("stage-mismatch-line", "children"),
        Input("stage-select", "value"),
        Input("result-store", "data"),
    )
    def warn_stage_mismatch(stage_id, result_data):
        if not result_data or not stage_id:
            return ""
        last_stage = result_data.get("stage_id")
        if last_stage and last_stage != stage_id:
            return (
                f"Plots show the last run ({last_stage}); "
                "press Run Simulation to simulate the selected stage."
            )
        return ""

    @callback(
        Output("ina-gain-control", "style"),
        Input("stage-select", "value"),
    )
    def toggle_ina_gain_control(stage_id):
        stage = get_stage(stage_id) if stage_id else None
        if stage and stage.fixed_rg:
            return {"display": "block"}
        return {"display": "none"}

    @callback(
        Output("bench-select", "options"),
        Output("bench-select", "value"),
        Input("stage-select", "value"),
        State("bench-select", "value"),
    )
    def update_bench_options(stage_id, current_bench):
        if not stage_id:
            return [], None
        stage = get_stage(stage_id)
        options = _bench_options(stage_id)
        values = [o["value"] for o in options]
        if current_bench in values:
            return options, current_bench
        return options, stage.default_bench if stage.default_bench in values else values[0]

    @callback(
        Output("gain-control", "style"),
        Input("stage-select", "value"),
    )
    def toggle_gain_control(stage_id):
        if not stage_id:
            return {"display": "none"}
        stage = get_stage(stage_id)
        if stage.patches_rg:
            return {"display": "block"}
        return {"display": "none"}

    @callback(
        Output("vref", "value"),
        Output("vthresh", "value"),
        Output("vdd", "value"),
        Output("ina-gain", "value"),
        Output("sanity-gain", "value"),
        Input("stage-select", "value"),
    )
    def update_circuit_defaults(stage_id):
        if not stage_id:
            return no_update, no_update, no_update, no_update, no_update
        stage = get_stage(stage_id)
        gain_default = str(int(default_ina_gain(stage_id)))
        return (
            str(stage.default_vref),
            str(stage.default_vthresh),
            str(stage.default_vdd),
            gain_default if stage.fixed_rg else no_update,
            gain_default if stage.patches_rg else no_update,
        )

    @callback(
        Output("ina-r3", "value"),
        Input("ina-gain", "value"),
    )
    def update_ina_r3(ina_gain):
        gain = parse_ina_gain(ina_gain, int(RECOMMENDED_GAIN))
        return r3_display_for_gain(gain)

    @callback(
        Output("sanity-r3", "value"),
        Input("sanity-gain", "value"),
    )
    def update_sanity_r3(sanity_gain):
        gain = parse_float(sanity_gain, 100.0)
        return r3_display_for_gain(max(gain, 2.0))

    @callback(
        Output("c-couple", "value"),
        Output("r-series", "value"),
        Output("r-vref", "value"),
        Output("r-diff", "value"),
        Output("c-diff", "value"),
        Output("c-out", "value"),
        Output("r-comp", "value"),
        Output("r-hyst", "value"),
        Output("ina-gain", "value"),
        Output("sanity-gain", "value"),
        Input("component-defaults", "value"),
        prevent_initial_call=True,
    )
    def apply_component_defaults_preset(preset_id):
        if not preset_id:
            return tuple(no_update for _ in range(10))
        preset = get_component_defaults(preset_id)
        gain_str = str(int(preset.gain))
        return (
            preset.c_couple,
            preset.r_series,
            preset.r_vref,
            preset.r_diff,
            preset.c_diff,
            preset.c_out,
            preset.r_comp,
            preset.r_hyst,
            gain_str,
            gain_str,
        )

    @callback(
        Output("settings-report-pre", "children"),
        Output("settings-report-text", "data"),
        Input("stage-select", "value"),
        Input("bench-select", "value"),
        Input("component-defaults", "value"),
        Input("pulse-rate-khz", "value"),
        Input("pulse-mv", "value"),
        Input("pulse-shape", "value"),
        Input("pulse-width-us", "value"),
        Input("num-pulses", "value"),
        Input("duration-ms", "value"),
        Input("lf-offset-enabled", "value"),
        Input("lf-offset-mv", "value"),
        Input("lf-offset-center-hz", "value"),
        Input("lf-offset-span-hz", "value"),
        Input("lf-offset-seed", "value"),
        Input("c-couple", "value"),
        Input("r-series", "value"),
        Input("r-vref", "value"),
        Input("r-diff", "value"),
        Input("c-diff", "value"),
        Input("electrode-mismatch", "value"),
        Input("c-out", "value"),
        Input("r-comp", "value"),
        Input("r-hyst", "value"),
        Input("vref", "value"),
        Input("vthresh", "value"),
        Input("vdd", "value"),
        Input("ina-gain", "value"),
        Input("sanity-gain", "value"),
        Input("view-mode", "value"),
    )
    def update_settings_report(*args):
        state = _gui_state_from_inputs(*args)
        text = format_settings_report(state)
        return text, text

    app.clientside_callback(
        """
        function(n_clicks, text) {
            if (!n_clicks || !text) {
                return window.dash_clientside.no_update;
            }
            navigator.clipboard.writeText(text);
            return "Copied to clipboard";
        }
        """,
        Output("copy-feedback", "children"),
        Input("settings-report", "n_clicks"),
        State("settings-report-text", "data"),
        prevent_initial_call=True,
    )

    @callback(
        Output("result-store", "data"),
        Output("status-line", "children"),
        Output("metrics-line", "children"),
        Input("run-button", "n_clicks"),
        State("stage-select", "value"),
        State("bench-select", "value"),
        State("component-defaults", "value"),
        State("pulse-rate-khz", "value"),
        State("pulse-mv", "value"),
        State("pulse-shape", "value"),
        State("pulse-width-us", "value"),
        State("num-pulses", "value"),
        State("duration-ms", "value"),
        State("lf-offset-enabled", "value"),
        State("lf-offset-mv", "value"),
        State("lf-offset-center-hz", "value"),
        State("lf-offset-span-hz", "value"),
        State("lf-offset-seed", "value"),
        State("c-couple", "value"),
        State("r-series", "value"),
        State("r-vref", "value"),
        State("r-diff", "value"),
        State("c-diff", "value"),
        State("electrode-mismatch", "value"),
        State("c-out", "value"),
        State("r-comp", "value"),
        State("r-hyst", "value"),
        State("vref", "value"),
        State("vthresh", "value"),
        State("vdd", "value"),
        State("ina-gain", "value"),
        State("sanity-gain", "value"),
        State("view-mode", "value"),
        prevent_initial_call=True,
    )
    def run_simulation_callback(n_clicks, *args):
        if not n_clicks:
            return no_update, no_update, no_update

        state = _gui_state_from_inputs(*args)
        try:
            run_result = run_simulation(state.to_run_config(project_root), project_root)
        except (
            NgspiceNotFoundError,
            NgspiceSimulationError,
            SimulationValidationError,
            ValueError,
            KeyError,
        ) as exc:
            # Keep the last good result so plots don't vanish on failure.
            status = html.Div(
                [
                    html.Span(f"Run failed: {exc}", style={"color": "crimson"}),
                    html.Br(),
                    html.Span(
                        "Showing the previous successful run (if any).",
                        style={"color": "#666", "fontSize": "12px"},
                    ),
                ]
            )
            return no_update, status, no_update

        metrics_parts = []
        if run_result.peak_vin_mv is not None:
            metrics_parts.append(f"Peak INA diff: {run_result.peak_vin_mv:.3f} mV")
        if run_result.measured_gain is not None:
            metrics_parts.append(f"Gain: {run_result.measured_gain:.2f} V/V")
        if state.stage_id == "03_detector" and run_result.vout_min_v is not None:
            metrics_parts.append(f"TRIGGER low: {run_result.vout_min_v:.3f} V")
            metrics_parts.append(f"TRIGGER high: {run_result.peak_vout_v:.3f} V")
        quality = run_result.quality
        if quality is not None and quality.stimulus_max_error_mv is not None:
            metrics_parts.append(
                f"Stimulus fidelity: {quality.stimulus_max_error_mv:.3f} mV max error"
            )

        result_data = {
            "raw_path": str(run_result.raw_path),
            "stage_id": state.stage_id,
            "sim_state": state.to_dict(),
        }
        if run_result.lf_offset is not None:
            result_data["lf_offset"] = asdict(run_result.lf_offset)

        status_text = (
            f"OK — {state.stage_id} ({state.bench_variant})  |  "
            f"{state.pulse_rate_khz:g} kHz  |  "
            f"{state.pulse_mv:g} mV  |  "
            f"{state.duration_ms:g} ms  |  "
            f"width {state.pulse_width_us:g} µs"
        )
        if run_result.lf_offset is not None:
            phase_deg = math.degrees(run_result.lf_offset.phase_rad)
            status_text += (
                f"  |  LF: {run_result.lf_offset.frequency_hz:.1f} Hz, "
                f"φ={phase_deg:.0f}°, {run_result.lf_offset.amplitude_mv:g} mV"
            )
        if state.electrode_mismatch_pct > 0:
            status_text += (
                f"  |  electrode model ON: Rs 15 kΩ, "
                f"{state.electrode_mismatch_pct:g}% mismatch"
            )

        children = [html.Span(status_text, style={"color": "green"})]
        if quality is not None:
            for warning in quality.warnings:
                children.append(html.Br())
                children.append(html.Span(f"Warning: {warning}", style={"color": "#b45309"}))
        return result_data, html.Div(children), " | ".join(metrics_parts)

    @callback(
        Output("main-plot", "figure"),
        Input("run-button", "n_clicks"),
        Input("plot-tabs", "value"),
        Input("view-mode", "value"),
        Input("result-store", "data"),
        State("stage-select", "value"),
        State("bench-select", "value"),
        State("component-defaults", "value"),
        State("pulse-rate-khz", "value"),
        State("pulse-mv", "value"),
        State("pulse-shape", "value"),
        State("pulse-width-us", "value"),
        State("num-pulses", "value"),
        State("duration-ms", "value"),
        State("lf-offset-enabled", "value"),
        State("lf-offset-mv", "value"),
        State("lf-offset-center-hz", "value"),
        State("lf-offset-span-hz", "value"),
        State("lf-offset-seed", "value"),
        State("c-couple", "value"),
        State("r-series", "value"),
        State("r-vref", "value"),
        State("r-diff", "value"),
        State("c-diff", "value"),
        State("electrode-mismatch", "value"),
        State("c-out", "value"),
        State("r-comp", "value"),
        State("r-hyst", "value"),
        State("vref", "value"),
        State("vthresh", "value"),
        State("vdd", "value"),
        State("ina-gain", "value"),
        State("sanity-gain", "value"),
    )
    def update_plot(
        _run_clicks,
        tab,
        view_mode,
        result_data,
        stage_id,
        bench_variant,
        component_defaults,
        pulse_rate_khz,
        pulse_mv,
        pulse_shape,
        pulse_width_us,
        num_pulses,
        duration_ms,
        lf_offset_enabled,
        lf_offset_mv,
        lf_offset_center_hz,
        lf_offset_span_hz,
        lf_offset_seed,
        c_couple,
        r_series,
        r_vref,
        r_diff,
        c_diff,
        electrode_mismatch,
        c_out,
        r_comp,
        r_hyst,
        vref,
        vthresh,
        vdd,
        ina_gain,
        sanity_gain,
    ):
        live_state = _gui_state_from_inputs(
            stage_id,
            bench_variant,
            component_defaults,
            pulse_rate_khz,
            pulse_mv,
            pulse_shape,
            pulse_width_us,
            num_pulses,
            duration_ms,
            lf_offset_enabled,
            lf_offset_mv,
            lf_offset_center_hz,
            lf_offset_span_hz,
            lf_offset_seed,
            c_couple,
            r_series,
            r_vref,
            r_diff,
            c_diff,
            electrode_mismatch,
            c_out,
            r_comp,
            r_hyst,
            vref,
            vthresh,
            vdd,
            ina_gain,
            sanity_gain,
            view_mode,
        )
        state = _state_for_plot(result_data, live_state)

        result_stage_id = result_data.get("stage_id", state.stage_id) if result_data else state.stage_id
        raw_path = result_data.get("raw_path") if result_data else None
        try:
            result = _load_result(raw_path, result_stage_id)
        except Exception as exc:  # corrupt/partial raw must never crash the GUI
            return _empty_figure(f"Could not load simulation result: {exc}")

        lf_offset = None
        if result_data and result_data.get("lf_offset"):
            lf_offset = LFOffsetParams(**result_data["lf_offset"])

        fig1, fig2, fig3 = build_all_figures(result, state, lf_offset=lf_offset)
        if tab == "tab-2":
            return fig2
        if tab == "tab-3":
            return fig3
        return fig1

    return app


def main(project_root: Path | None = None, host: str = "127.0.0.1", port: int = 8050, debug: bool = False):
    root = project_root or Path(__file__).resolve().parents[3]
    app = create_app(root)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
