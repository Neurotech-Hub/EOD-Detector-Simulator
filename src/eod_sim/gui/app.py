"""Plotly Dash application for EOD detector tuning."""

from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path

from dash import Dash, Input, Output, State, callback, dcc, html, no_update

from eod_sim.gui.state import GuiState, parse_float, parse_int, parse_optional_int, parse_spice_value
from eod_sim.gui.views import build_all_figures
from eod_sim.input_network import stage_has_input_network
from eod_sim.ngspice import NgspiceNotFoundError, NgspiceSimulationError
from eod_sim.results import SimulationResult, load_raw
from eod_sim.runner import run_simulation
from eod_sim.stages.registry import get_stage, list_stages

_INPUT_STYLE = {"width": "100%"}


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
    vref,
    vthresh,
    vdd,
    gain,
    view_mode,
) -> GuiState:
    enabled = bool(lf_offset_enabled) and "enabled" in (lf_offset_enabled or [])
    stage = get_stage(stage_id or "03_detector")
    return GuiState(
        stage_id=stage_id or "03_detector",
        bench_variant=bench_variant or stage.default_bench,
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
        c_diff=parse_spice_value(c_diff, "330p"),
        vref=parse_float(vref, 1.65),
        vthresh=parse_float(vthresh, 1.85),
        vdd=parse_float(vdd, 3.3),
        gain=parse_float(gain, 100.0),
        view_mode=view_mode or "pulse",
    )


def _state_for_plot(result_data: dict | None, live_state: GuiState) -> GuiState:
    """Use simulation params from last run; keep live view controls."""
    if result_data and result_data.get("sim_state"):
        sim = GuiState.from_dict(result_data["sim_state"])
        sim.view_mode = live_state.view_mode
        return sim
    return live_state


def _control_block() -> html.Div:
    default_stage = get_stage("03_detector")
    return html.Div(
        id="sidebar",
        style={
            "width": "300px",
            "padding": "16px",
            "borderRight": "1px solid #ddd",
            "overflowY": "auto",
        },
        children=[
            html.H3("Controls"),
            html.Label("Stage"),
            dcc.Dropdown(id="stage-select", options=_stage_options(), value="03_detector"),
            html.Br(),
            html.Label("Bench"),
            dcc.Dropdown(
                id="bench-select",
                options=_bench_options("03_detector"),
                value=default_stage.default_bench,
            ),
            html.Hr(),
            html.H4("Waveform"),
            html.Label("Pulse rate (kHz)"),
            _decimal_input("pulse-rate-khz", 0.5),
            html.Br(),
            html.Br(),
            html.Label("Pulse amplitude (mV)"),
            _decimal_input("pulse-mv", 300),
            html.Br(),
            html.Br(),
            html.Label("Pulse shape"),
            dcc.Dropdown(
                id="pulse-shape",
                options=[
                    {"label": "Rounded", "value": "rounded"},
                    {"label": "Square", "value": "square"},
                ],
                value="rounded",
            ),
            html.Br(),
            html.Label("Pulse width (µs)"),
            _decimal_input("pulse-width-us", 200),
            html.Br(),
            html.Br(),
            html.Label("Num pulses"),
            _decimal_input("num-pulses", 4),
            html.Br(),
            html.Br(),
            html.Label("Duration (ms)"),
            _decimal_input("duration-ms", 20),
            html.Br(),
            html.Br(),
            dcc.Checklist(
                id="lf-offset-enabled",
                options=[{"label": " Slow water offset (~20 Hz)", "value": "enabled"}],
                value=[],
                style={"marginBottom": "8px"},
            ),
            html.Div(
                id="lf-offset-controls",
                style={"display": "none"},
                children=[
                    html.Label("LF offset amplitude (mV)"),
                    _decimal_input("lf-offset-mv", 100),
                    html.Br(),
                    html.Br(),
                    html.Label("LF center frequency (Hz)"),
                    _decimal_input("lf-offset-center-hz", 20),
                    html.Br(),
                    html.Br(),
                    html.Label("LF frequency span ± (Hz)"),
                    _decimal_input("lf-offset-span-hz", 10),
                    html.Br(),
                    html.Br(),
                    html.Label("LF seed (optional)"),
                    dcc.Input(
                        id="lf-offset-seed",
                        type="text",
                        inputMode="numeric",
                        placeholder="random each run",
                        debounce=True,
                        style=_INPUT_STYLE,
                    ),
                    html.P(
                        "Each run draws f in [center−span, center+span] and a random phase vs first pulse.",
                        style={"fontSize": "12px", "color": "#666", "margin": "8px 0 0 0"},
                    ),
                ],
            ),
            html.Hr(),
            html.H4("Circuit"),
            html.Label("VREF (V)"),
            _decimal_input("vref", 1.65),
            html.Br(),
            html.Br(),
            html.Label("VTHRESH (V)"),
            _decimal_input("vthresh", 1.85),
            html.Br(),
            html.Br(),
            html.Label("VDD (V)"),
            _decimal_input("vdd", 3.3),
            html.Div(
                id="gain-control",
                style={"display": "none"},
                children=[
                    html.Br(),
                    html.Label("Gain (V/V)"),
                    _decimal_input("gain", 100),
                ],
            ),
            html.Hr(),
            html.Div(
                id="input-network-panel",
                children=[
                    html.H4("INA input network"),
                    html.P(
                        "Symmetric per-leg values; SPICE units (n, k, Meg, p).",
                        style={"fontSize": "12px", "color": "#666", "margin": "0 0 8px 0"},
                    ),
                    html.Label("Input coupling cap (C2/C3)"),
                    _spice_input("c-couple", "4.7n"),
                    html.Br(),
                    html.Br(),
                    html.Label("Series input resistor (R4/R7)"),
                    _spice_input("r-series", "100k"),
                    html.Br(),
                    html.Br(),
                    html.Label("VREF bias resistor (R6/R8)"),
                    _spice_input("r-vref", "10Meg"),
                    html.Br(),
                    html.Br(),
                    html.Label("Differential input resistor (R15)"),
                    _spice_input("r-diff", "1Meg"),
                    html.Br(),
                    html.Br(),
                    html.Label("Differential input capacitor (C4)"),
                    _spice_input("c-diff", "330p"),
                ],
            ),
            html.Hr(),
            html.H4("View"),
            dcc.RadioItems(
                id="view-mode",
                options=[
                    {"label": " Overview ", "value": "overview"},
                    {"label": " Single pulse ", "value": "pulse"},
                ],
                value="pulse",
                inline=True,
            ),
            html.P(
                "Single pulse: first pulse in the train; x-axis spans 2× pulse width.",
                style={"fontSize": "12px", "color": "#666", "margin": "6px 0 12px 0"},
            ),
            html.Button("Run Simulation", id="run-button", n_clicks=0, style={"width": "100%"}),
            html.Div(id="status-line", style={"marginTop": "12px", "fontSize": "13px", "color": "#444"}),
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
                                    dcc.Tab(label="Input vs ELEC_OUT", value="tab-1"),
                                    dcc.Tab(label="Input vs COMP_IN", value="tab-2"),
                                    dcc.Tab(label="Comparator", value="tab-3"),
                                ],
                            ),
                            dcc.Graph(id="main-plot", style={"height": "calc(100vh - 140px)"}),
                            html.Div(id="metrics-line", style={"fontSize": "13px", "color": "#333", "marginTop": "8px"}),
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
        Input("stage-select", "value"),
    )
    def update_circuit_defaults(stage_id):
        if not stage_id:
            return no_update, no_update, no_update
        stage = get_stage(stage_id)
        return str(stage.default_vref), str(stage.default_vthresh), str(stage.default_vdd)

    @callback(
        Output("result-store", "data"),
        Output("status-line", "children"),
        Output("metrics-line", "children"),
        Input("run-button", "n_clicks"),
        State("stage-select", "value"),
        State("bench-select", "value"),
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
        State("vref", "value"),
        State("vthresh", "value"),
        State("vdd", "value"),
        State("gain", "value"),
        State("view-mode", "value"),
        prevent_initial_call=True,
    )
    def run_simulation_callback(n_clicks, *args):
        if not n_clicks:
            return no_update, no_update, no_update

        state = _gui_state_from_inputs(*args)
        try:
            run_result = run_simulation(state.to_run_config(project_root), project_root)
        except (NgspiceNotFoundError, NgspiceSimulationError, ValueError, KeyError) as exc:
            return None, html.Span(str(exc), style={"color": "crimson"}), ""

        metrics_parts = []
        if run_result.peak_vin_mv is not None:
            metrics_parts.append(f"Peak INA diff: {run_result.peak_vin_mv:.3f} mV")
        if run_result.measured_gain is not None:
            metrics_parts.append(f"Gain: {run_result.measured_gain:.2f} V/V")
        if state.stage_id == "03_detector" and run_result.vout_min_v is not None:
            metrics_parts.append(f"TRIGGER low: {run_result.vout_min_v:.3f} V")
            metrics_parts.append(f"TRIGGER high: {run_result.peak_vout_v:.3f} V")

        result_data = {
            "raw_path": str(run_result.raw_path),
            "stage_id": state.stage_id,
            "sim_state": state.to_dict(),
        }
        if run_result.lf_offset is not None:
            result_data["lf_offset"] = asdict(run_result.lf_offset)

        status_text = (
            f"OK — {run_result.raw_path.name}  |  "
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
        status = html.Span(status_text, style={"color": "green"})
        return result_data, status, " | ".join(metrics_parts)

    @callback(
        Output("main-plot", "figure"),
        Input("run-button", "n_clicks"),
        Input("plot-tabs", "value"),
        Input("view-mode", "value"),
        Input("result-store", "data"),
        State("stage-select", "value"),
        State("bench-select", "value"),
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
        State("vref", "value"),
        State("vthresh", "value"),
        State("vdd", "value"),
        State("gain", "value"),
    )
    def update_plot(
        _run_clicks,
        tab,
        view_mode,
        result_data,
        stage_id,
        bench_variant,
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
        vref,
        vthresh,
        vdd,
        gain,
    ):
        live_state = _gui_state_from_inputs(
            stage_id,
            bench_variant,
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
            vref,
            vthresh,
            vdd,
            gain,
            view_mode,
        )
        state = _state_for_plot(result_data, live_state)

        result_stage_id = result_data.get("stage_id", state.stage_id) if result_data else state.stage_id
        raw_path = result_data.get("raw_path") if result_data else None
        result = _load_result(raw_path, result_stage_id)

        fig1, fig2, fig3 = build_all_figures(result, state)
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
