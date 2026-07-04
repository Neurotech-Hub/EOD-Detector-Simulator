"""GUI session state and mapping to simulation runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from eod_sim.input_network import InputNetworkParams
from eod_sim.runner import RunConfig
from eod_sim.stages.registry import Stage, get_stage
from eod_sim.waveforms import isi_ms_from_khz

ViewMode = Literal["overview", "pulse"]
PulseShape = Literal["square", "rounded"]

GUI_TUNING_STAGES = ("02_frontend", "03_detector")


@dataclass
class GuiState:
    """User-adjustable parameters for the tuning GUI."""

    stage_id: str = "03_detector"
    bench_variant: str = "ti"
    pulse_rate_khz: float = 0.5
    pulse_mv: float = 300.0
    pulse_shape: PulseShape = "rounded"
    pulse_width_us: float = 200.0
    num_pulses: int = 4
    duration_ms: float = 20.0
    start_ms: float = 5.0
    vref: float = 1.65
    vthresh: float = 1.85
    vdd: float = 3.3
    gain: float = 100.0
    pulse_index: int = 0
    view_mode: ViewMode = "pulse"
    pulse_window_scale: float = 2.0
    output_root: str | None = None
    lf_offset_enabled: bool = False
    lf_offset_amplitude_mv: float = 100.0
    lf_offset_center_hz: float = 20.0
    lf_offset_span_hz: float = 10.0
    lf_offset_seed: int | None = None
    c_couple: str = "4.7n"
    r_series: str = "100k"
    r_vref: str = "10Meg"
    r_diff: str = "1Meg"
    c_diff: str = "330p"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GuiState:
        if not data:
            return cls()
        fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in fields})

    def stage(self) -> Stage:
        return get_stage(self.stage_id)

    def isi_ms(self) -> float:
        return isi_ms_from_khz(self.pulse_rate_khz)

    def apply_stage_defaults(self, stage_id: str) -> GuiState:
        stage = get_stage(stage_id)
        benches = list(stage.benches)
        return GuiState(
            **{
                **self.to_dict(),
                "stage_id": stage_id,
                "bench_variant": stage.default_bench if stage.default_bench in benches else benches[0],
                "vref": stage.default_vref,
                "vthresh": stage.default_vthresh,
                "vdd": stage.default_vdd,
            }
        )

    def to_run_config(self, project_root: Path | None = None) -> RunConfig:
        root = Path(self.output_root) if self.output_root else project_root
        return RunConfig(
            stage_id=self.stage_id,
            bench_variant=self.bench_variant,
            gain=self.gain,
            pulse_mv=self.pulse_mv,
            pulse_shape=self.pulse_shape,
            pulse_width_us=self.pulse_width_us,
            isi_ms=self.isi_ms(),
            num_pulses=self.num_pulses,
            duration_ms=self.duration_ms,
            pulse_index=self.pulse_index,
            pulse_margin_us=None,
            pulse_zoom=False,
            plot_backend="plotly",
            output_root=root / "outputs" if root else None,
            vref=self.vref,
            vthresh=self.vthresh,
            vdd=self.vdd,
            lf_offset_enabled=self.lf_offset_enabled,
            lf_offset_amplitude_mv=self.lf_offset_amplitude_mv,
            lf_offset_center_hz=self.lf_offset_center_hz,
            lf_offset_span_hz=self.lf_offset_span_hz,
            lf_offset_seed=self.lf_offset_seed,
            input_network=InputNetworkParams(
                c_couple=self.c_couple,
                r_series=self.r_series,
                r_vref=self.r_vref,
                r_diff=self.r_diff,
                c_diff=self.c_diff,
            ),
        )


def stage_supports_tab(stage_id: str, tab: int) -> bool:
    """Return whether a GUI analysis tab is available for the stage."""
    if tab in (1, 2):
        return stage_id in ("02_frontend", "03_detector")
    if tab == 3:
        return stage_id == "03_detector"
    return False


def parse_spice_value(value: object, default: str) -> str:
    """Parse a SPICE literal text input; fall back when empty."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def parse_float(value: object, default: float) -> float:
    """Parse a Dash input value; fall back when empty or invalid."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_optional_int(value: object) -> int | None:
    """Parse optional int; empty or invalid input returns None."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_int(value: object, default: int) -> int:
    """Parse a Dash input value as int; fall back when empty or invalid."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        return default
