"""Visualization of INA333 simulation results."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from eod_sim.results import SimulationResult


def _time_ms(time_s):
    return time_s * 1e3


def plot_matplotlib(
    result: SimulationResult,
    output_path: Path,
    gain: float,
    title: str = "INA333 EOD Pulse Response",
) -> Path:
    """Save a two-panel matplotlib figure of input and output waveforms."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    t_ms = _time_ms(result.time_s)

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    fig.suptitle(title, fontsize=14)

    axes[0].plot(t_ms, result.vin_diff * 1e3, color="#2563eb", linewidth=1.2)
    axes[0].set_ylabel("Vin diff (mV)")
    axes[0].set_title("Differential Input")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(t_ms, result.out, color="#dc2626", linewidth=1.2)
    axes[1].set_ylabel("Vout (V)")
    axes[1].set_xlabel("Time (ms)")
    axes[1].set_title(f"Output (gain = {gain:.1f} V/V)")
    axes[1].grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def plot_plotly(
    result: SimulationResult,
    output_path: Path,
    gain: float,
    title: str = "INA333 EOD Pulse Response",
) -> Path:
    """Save an interactive two-panel Plotly HTML figure."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    t_ms = _time_ms(result.time_s)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=("Differential Input", f"Output (gain = {gain:.1f} V/V)"),
        vertical_spacing=0.1,
    )

    fig.add_trace(
        go.Scatter(
            x=t_ms,
            y=result.vin_diff * 1e3,
            mode="lines",
            name="Vin diff (mV)",
            line=dict(color="#2563eb"),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=t_ms,
            y=result.out,
            mode="lines",
            name="Vout (V)",
            line=dict(color="#dc2626"),
        ),
        row=2,
        col=1,
    )

    fig.update_xaxes(title_text="Time (ms)", row=2, col=1)
    fig.update_yaxes(title_text="Vin diff (mV)", row=1, col=1)
    fig.update_yaxes(title_text="Vout (V)", row=2, col=1)
    fig.update_layout(title=title, height=700, showlegend=False)

    fig.write_html(str(output_path))
    return output_path


def plot_waveforms(
    result: SimulationResult,
    output_dir: Path,
    gain: float,
    backend: str = "matplotlib",
    model: str = "ideal",
) -> Path:
    """Plot input and output waveforms using the selected backend."""
    model_label = model.upper() if model == "ti" else model.capitalize()
    title = f"INA333 EOD Pulse Response ({model_label} model)"
    stem = f"ina333_waveforms_{model}"

    if backend == "matplotlib":
        return plot_matplotlib(result, output_dir / f"{stem}.png", gain, title=title)
    if backend == "plotly":
        return plot_plotly(result, output_dir / f"{stem}.html", gain, title=title)
    raise ValueError(f"Unknown plot backend: {backend}")
