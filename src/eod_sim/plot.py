"""Visualization of simulation results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from eod_sim.constants import OVERVIEW_TRIM_MS
from eod_sim.results import SimulationResult
from eod_sim.stages.registry import Stage


@dataclass
class PulseViewConfig:
    """Time window and labeling for a single-pulse zoom plot."""

    pulse_onset_s: float
    t_start_s: float
    t_end_s: float
    pulse_index: int = 0


def _overview_mask(time_s: np.ndarray) -> np.ndarray:
    """Drop the first OVERVIEW_TRIM_MS of transient startup artifacts."""
    return time_s >= OVERVIEW_TRIM_MS * 1e-3


def _time_ms(time_s: np.ndarray) -> np.ndarray:
    return time_s * 1e3


def _time_us_from_onset(time_s: np.ndarray, pulse_onset_s: float) -> np.ndarray:
    return (time_s - pulse_onset_s) * 1e6


def _output_subtitle(gain: float | None) -> str:
    if gain is None:
        return "Output"
    return f"Output (gain = {gain:.1f} V/V)"


def _resolve_node(result: SimulationResult, nodes: dict[str, str], key: str) -> str:
    return nodes.get(key, key)


Stimulus = tuple[np.ndarray, np.ndarray]
"""Commanded stimulus overlay: (time_s, differential volts)."""


def _stimulus_overlay(
    stage: Stage,
    input_keys: tuple[str, str],
    stimulus: Stimulus | None,
) -> Stimulus | None:
    """Return the stimulus overlay if the plotted input is the driven pair.

    The commanded waveform is only comparable to the trace when the plot
    shows the filesource-driven nodes; comparing it against downstream nodes
    (e.g. INA inputs after the HPF) would be misleading.
    """
    if stimulus is None:
        return None
    nodes = stage.resolved_signal_nodes()
    plotted = (nodes.get(input_keys[0], input_keys[0]), nodes.get(input_keys[1], input_keys[1]))
    if plotted != stage.driven_nodes():
        return None
    return stimulus


def _trace_for_key(
    result: SimulationResult,
    nodes: dict[str, str],
    key: str,
) -> np.ndarray:
    spice_node = _resolve_node(result, nodes, key)
    return result.node_voltage(spice_node)


def _trace_pair(
    result: SimulationResult,
    nodes: dict[str, str],
    pos_key: str,
    neg_key: str,
) -> np.ndarray:
    return _trace_for_key(result, nodes, pos_key) - _trace_for_key(result, nodes, neg_key)


def _trace_output(
    result: SimulationResult,
    nodes: dict[str, str],
    output: str | tuple[str, str],
    mode: str,
) -> np.ndarray:
    if isinstance(output, tuple):
        return _trace_pair(result, nodes, output[0], output[1])
    if mode == "relative":
        ref_node = _resolve_node(result, nodes, "ref")
        return result.node_voltage(output) - result.node_voltage(ref_node)
    if mode == "diff":
        raise ValueError("diff mode requires a tuple output pair")
    return result.node_voltage(_resolve_node(result, nodes, output))


def slice_pulse_window(
    result: SimulationResult,
    t_start_s: float,
    t_end_s: float,
    left: np.ndarray,
    right: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return time and left/right traces within [t_start, t_end]."""
    mask = (result.time_s >= t_start_s) & (result.time_s <= t_end_s)
    return result.time_s[mask], left[mask], right[mask]


def plot_single_pulse_matplotlib(
    result: SimulationResult,
    output_path: Path,
    view: PulseViewConfig,
    stage: Stage,
    gain: float | None,
    title: str,
    stimulus: Stimulus | None = None,
) -> Path:
    """Save a dual-axis single-pulse figure."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nodes = stage.resolved_signal_nodes()
    left_keys = stage.pulse_zoom_left or stage.overview_input
    left = _trace_pair(result, nodes, left_keys[0], left_keys[1])
    right = _trace_output(result, nodes, stage.pulse_zoom_right, stage.pulse_zoom_right_mode)

    time_s, left_w, right_w = slice_pulse_window(
        result, view.t_start_s, view.t_end_s, left, right
    )
    t_us = _time_us_from_onset(time_s, view.pulse_onset_s)

    fig, ax_left = plt.subplots(figsize=(10, 5))
    ax_right = ax_left.twinx()

    left_label = stage.input_label
    right_label = stage.output_label or "Output"
    if stage.pulse_zoom_right_mode == "relative":
        right_label = f"{right_label} − REF"

    overlay_lines = []
    overlay = _stimulus_overlay(stage, left_keys, stimulus)
    if overlay is not None:
        s_t, s_v = overlay
        s_mask = (s_t >= view.t_start_s) & (s_t <= view.t_end_s)
        overlay_lines = ax_left.plot(
            _time_us_from_onset(s_t[s_mask], view.pulse_onset_s),
            s_v[s_mask] * 1e3,
            color="#94a3b8",
            linewidth=1.2,
            linestyle="--",
            label="Commanded stimulus",
        )

    line_left = ax_left.plot(t_us, left_w * 1e3, color="#2563eb", linewidth=1.5, label=left_label)
    line_right = ax_right.plot(
        t_us, right_w * 1e3, color="#dc2626", linewidth=1.5, label=right_label
    )

    ax_left.set_xlabel("Time from pulse onset (µs)")
    ax_left.set_ylabel(f"{left_label} (mV)", color="#2563eb")
    ax_right.set_ylabel(f"{right_label} (mV)", color="#dc2626")
    ax_left.tick_params(axis="y", labelcolor="#2563eb")
    ax_right.tick_params(axis="y", labelcolor="#dc2626")
    ax_left.grid(True, alpha=0.3)
    ax_left.set_title(f"{title} — pulse {view.pulse_index + 1}")

    lines = overlay_lines + line_left + line_right
    ax_left.legend(lines, [line.get_label() for line in lines], loc="upper right")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_single_pulse_plotly(
    result: SimulationResult,
    output_path: Path,
    view: PulseViewConfig,
    stage: Stage,
    gain: float | None,
    title: str,
    stimulus: Stimulus | None = None,
) -> Path:
    """Save an interactive dual-axis single-pulse HTML figure."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nodes = stage.resolved_signal_nodes()
    left_keys = stage.pulse_zoom_left or stage.overview_input
    left = _trace_pair(result, nodes, left_keys[0], left_keys[1])
    right = _trace_output(result, nodes, stage.pulse_zoom_right, stage.pulse_zoom_right_mode)

    time_s, left_w, right_w = slice_pulse_window(
        result, view.t_start_s, view.t_end_s, left, right
    )
    t_us = _time_us_from_onset(time_s, view.pulse_onset_s)

    left_label = stage.input_label
    right_label = stage.output_label or "Output"
    if stage.pulse_zoom_right_mode == "relative":
        right_label = f"{right_label} − REF"

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    overlay = _stimulus_overlay(stage, left_keys, stimulus)
    if overlay is not None:
        s_t, s_v = overlay
        s_mask = (s_t >= view.t_start_s) & (s_t <= view.t_end_s)
        fig.add_trace(
            go.Scatter(
                x=_time_us_from_onset(s_t[s_mask], view.pulse_onset_s),
                y=s_v[s_mask] * 1e3,
                mode="lines",
                name="Commanded stimulus",
                line=dict(color="#94a3b8", dash="dash"),
            ),
            secondary_y=False,
        )
    fig.add_trace(
        go.Scatter(x=t_us, y=left_w * 1e3, mode="lines", name=left_label, line=dict(color="#2563eb")),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=t_us, y=right_w * 1e3, mode="lines", name=right_label, line=dict(color="#dc2626")),
        secondary_y=True,
    )

    fig.update_xaxes(title_text="Time from pulse onset (µs)")
    fig.update_yaxes(title_text=f"{left_label} (mV)", secondary_y=False, color="#2563eb")
    fig.update_yaxes(title_text=f"{right_label} (mV)", secondary_y=True, color="#dc2626")
    fig.update_layout(
        title=f"{title} — pulse {view.pulse_index + 1}<br><sup>{_output_subtitle(gain)}</sup>",
        height=500,
        legend=dict(x=0.99, y=0.99, xanchor="right"),
    )
    fig.write_html(str(output_path))
    return output_path


def plot_single_pulse(
    result: SimulationResult,
    output_dir: Path,
    view: PulseViewConfig,
    stage: Stage,
    gain: float | None,
    backend: str,
    bench_variant: str,
    stimulus: Stimulus | None = None,
) -> Path:
    """Plot a single-pulse dual-axis view using the selected backend."""
    variant_label = bench_variant.upper() if bench_variant == "ti" else bench_variant.capitalize()
    title = f"{stage.id} ({variant_label})"
    stem = f"{stage.id}_pulse{view.pulse_index + 1}_{bench_variant}"

    if backend == "matplotlib":
        return plot_single_pulse_matplotlib(
            result, output_dir / f"{stem}.png", view, stage, gain, title=title, stimulus=stimulus
        )
    if backend == "plotly":
        return plot_single_pulse_plotly(
            result, output_dir / f"{stem}.html", view, stage, gain, title=title, stimulus=stimulus
        )
    raise ValueError(f"Unknown plot backend: {backend}")


def plot_matplotlib(
    result: SimulationResult,
    output_path: Path,
    stage: Stage,
    gain: float | None,
    title: str,
    stimulus: Stimulus | None = None,
) -> Path:
    """Save a two-panel matplotlib figure of input and output waveforms."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nodes = stage.resolved_signal_nodes()
    trim = _overview_mask(result.time_s)
    t_ms = _time_ms(result.time_s[trim])

    top = _trace_pair(result, nodes, stage.overview_input[0], stage.overview_input[1])[trim]
    bottom = _trace_output(
        result, nodes, stage.overview_output, stage.overview_bottom_mode
    )[trim]

    bottom_title = stage.output_label or _output_subtitle(gain)
    if stage.overview_bottom_mode == "relative":
        bottom_title = f"{bottom_title} − REF"
    elif stage.overview_bottom_mode == "diff" and isinstance(stage.overview_output, tuple):
        bottom_title = stage.output_label or "Output differential"

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.suptitle(title, fontsize=14)

    overlay = _stimulus_overlay(stage, stage.overview_input, stimulus)
    if overlay is not None:
        s_t, s_v = overlay
        s_mask = _overview_mask(s_t)
        axes[0].plot(
            _time_ms(s_t[s_mask]),
            s_v[s_mask] * 1e3,
            color="#94a3b8",
            linewidth=1.0,
            linestyle="--",
            label="Commanded stimulus",
        )

    axes[0].plot(t_ms, top * 1e3, color="#2563eb", linewidth=1.2, label=stage.input_label)
    axes[0].set_ylabel("mV")
    axes[0].set_title(stage.input_label)
    if overlay is not None:
        axes[0].legend(loc="upper right", fontsize=8)
    axes[0].grid(True, alpha=0.3)

    if stage.comparator_stage and stage.overview_bottom_mode == "absolute":
        axes[1].plot(t_ms, bottom, color="#dc2626", linewidth=1.2)
        axes[1].set_ylabel("V")
    else:
        axes[1].plot(t_ms, bottom * 1e3, color="#dc2626", linewidth=1.2)
        axes[1].set_ylabel("mV")

    axes[1].set_xlabel("Time (ms)")
    axes[1].set_title(bottom_title)
    axes[1].grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_plotly(
    result: SimulationResult,
    output_path: Path,
    stage: Stage,
    gain: float | None,
    title: str,
    stimulus: Stimulus | None = None,
) -> Path:
    """Save an interactive two-panel Plotly HTML figure."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nodes = stage.resolved_signal_nodes()
    trim = _overview_mask(result.time_s)
    t_ms = _time_ms(result.time_s[trim])

    top = _trace_pair(result, nodes, stage.overview_input[0], stage.overview_input[1])[trim]
    bottom = _trace_output(
        result, nodes, stage.overview_output, stage.overview_bottom_mode
    )[trim]

    bottom_title = stage.output_label or _output_subtitle(gain)
    if stage.overview_bottom_mode == "relative":
        bottom_title = f"{bottom_title} − REF"

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=(stage.input_label, bottom_title),
        vertical_spacing=0.1,
    )

    overlay = _stimulus_overlay(stage, stage.overview_input, stimulus)
    if overlay is not None:
        s_t, s_v = overlay
        s_mask = _overview_mask(s_t)
        fig.add_trace(
            go.Scatter(
                x=_time_ms(s_t[s_mask]),
                y=s_v[s_mask] * 1e3,
                mode="lines",
                name="Commanded stimulus",
                line=dict(color="#94a3b8", dash="dash"),
            ),
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Scatter(x=t_ms, y=top * 1e3, mode="lines", name="Input (mV)", line=dict(color="#2563eb")),
        row=1,
        col=1,
    )

    if stage.comparator_stage and stage.overview_bottom_mode == "absolute":
        fig.add_trace(
            go.Scatter(x=t_ms, y=bottom, mode="lines", name="Output (V)", line=dict(color="#dc2626")),
            row=2,
            col=1,
        )
    else:
        fig.add_trace(
            go.Scatter(x=t_ms, y=bottom * 1e3, mode="lines", name="Output (mV)", line=dict(color="#dc2626")),
            row=2,
            col=1,
        )

    fig.update_xaxes(title_text="Time (ms)", row=2, col=1)
    fig.update_yaxes(title_text="mV", row=1, col=1)
    fig.update_yaxes(
        title_text="V" if stage.comparator_stage and stage.overview_bottom_mode == "absolute" else "mV",
        row=2,
        col=1,
    )
    fig.update_layout(title=title, height=700, showlegend=False)
    fig.write_html(str(output_path))
    return output_path


def plot_waveforms(
    result: SimulationResult,
    output_dir: Path,
    stage: Stage,
    gain: float | None = None,
    backend: str = "matplotlib",
    bench_variant: str = "ideal",
    stimulus: Stimulus | None = None,
) -> Path:
    """Plot input and output waveforms using the selected backend."""
    variant_label = bench_variant.upper() if bench_variant == "ti" else bench_variant.capitalize()
    title = f"{stage.id} ({variant_label})"
    stem = f"{stage.id}_waveforms_{bench_variant}"

    if backend == "matplotlib":
        return plot_matplotlib(
            result, output_dir / f"{stem}.png", stage, gain, title=title, stimulus=stimulus
        )
    if backend == "plotly":
        return plot_plotly(
            result, output_dir / f"{stem}.html", stage, gain, title=title, stimulus=stimulus
        )
    raise ValueError(f"Unknown plot backend: {backend}")
