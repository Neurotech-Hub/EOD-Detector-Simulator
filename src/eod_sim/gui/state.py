"""GUI session state and mapping to simulation runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from eod_sim.comparator_network import ComparatorNetworkParams, stage_has_comparator_network
from eod_sim.input_network import InputNetworkParams, stage_has_input_network
from eod_sim.runner import RunConfig
from eod_sim.stages.registry import Stage, get_stage
from eod_sim.waveforms import format_rg_spice, gain_to_rg, isi_ms_from_khz

ViewMode = Literal["overview", "pulse"]
PulseShape = Literal["square", "rounded", "recorded"]
ComponentDefaultsId = Literal["detector_v3", "detector_v3_no_c4", "ideal_v3"]

GUI_TUNING_STAGES = ("02_frontend", "03_detector")

# Sim-derived recommended values (README + C4_STABILITY.md).
# C5 is removed per the bench-confirmed oscillation finding; 1 fF is
# effectively an open (same convention as NO_C4_DIFF).
RECOMMENDED_GAIN = 3.0
RECOMMENDED_C_DIFF = "47p"
RECOMMENDED_C_OUT = "1f"

# KiCad EOD_Detector_v3-1 stock (R3 = 100k → G = 2).
DETECTOR_V3_GAIN = 2.0

# Absent C4: 1 fF is effectively an open between INA+ and INA− in transient sims.
NO_C4_DIFF = "1f"


@dataclass(frozen=True)
class ComponentDefaultsPreset:
    """Board or sim-recommended passive/network values."""

    label: str
    gain: float
    c_couple: str
    r_series: str
    r_vref: str
    r_diff: str
    c_diff: str
    c_out: str
    r_comp: str
    r_hyst: str


COMPONENT_DEFAULTS: dict[str, ComponentDefaultsPreset] = {
    "detector_v3": ComponentDefaultsPreset(
        label="Detector v3",
        gain=DETECTOR_V3_GAIN,
        c_couple="4.7n",
        r_series="100k",
        r_vref="10Meg",
        r_diff="1Meg",
        c_diff="330p",
        c_out="2.2n",
        r_comp="4.7k",
        r_hyst="1Meg",
    ),
    "detector_v3_no_c4": ComponentDefaultsPreset(
        label="Detector v3 - No C4",
        gain=DETECTOR_V3_GAIN,
        c_couple="4.7n",
        r_series="100k",
        r_vref="10Meg",
        r_diff="1Meg",
        c_diff=NO_C4_DIFF,
        c_out="2.2n",
        r_comp="4.7k",
        r_hyst="1Meg",
    ),
    "ideal_v3": ComponentDefaultsPreset(
        label="Ideal v3",
        gain=RECOMMENDED_GAIN,
        c_couple="4.7n",
        r_series="100k",
        r_vref="10Meg",
        r_diff="1Meg",
        c_diff=RECOMMENDED_C_DIFF,
        c_out=RECOMMENDED_C_OUT,
        r_comp="4.7k",
        r_hyst="1Meg",
    ),
}


def get_component_defaults(preset_id: str) -> ComponentDefaultsPreset:
    """Return a component-defaults preset; unknown ids fall back to Ideal v3."""
    return COMPONENT_DEFAULTS.get(preset_id, COMPONENT_DEFAULTS["ideal_v3"])


@dataclass
class GuiState:
    """User-adjustable parameters for the tuning GUI."""

    stage_id: str = "03_detector"
    bench_variant: str = "ti"
    component_defaults: ComponentDefaultsId = "ideal_v3"
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
    gain: float = RECOMMENDED_GAIN
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
    c_diff: str = RECOMMENDED_C_DIFF
    electrode_mismatch_pct: float = 0.0
    c_out: str = RECOMMENDED_C_OUT
    r_comp: str = "4.7k"
    r_hyst: str = "1Meg"

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
                "gain": default_ina_gain(stage_id),
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
                electrode_mismatch_pct=self.electrode_mismatch_pct,
            ),
            comparator_network=ComparatorNetworkParams(
                c_out=self.c_out,
                r_comp=self.r_comp,
                r_hyst=self.r_hyst,
            ),
        )


def default_ina_gain(stage_id: str) -> float:
    """Default INA333 gain (V/V) for a stage."""
    stage = get_stage(stage_id)
    if stage.patches_rg:
        return 100.0
    if stage.fixed_rg:
        return RECOMMENDED_GAIN
    return RECOMMENDED_GAIN


def r3_spice_for_gain(gain: float) -> str:
    """SPICE literal for R3 (RG) at the given INA333 gain."""
    return format_rg_spice(gain_to_rg(gain))


def r3_display_for_gain(gain: float) -> str:
    """Human-readable R3 value for the GUI readout."""
    return r3_spice_for_gain(gain)


def format_settings_report(state: GuiState) -> str:
    """Plain-text summary of current simulator settings (click-to-copy)."""
    lines = [
        "EOD Detector — simulation settings",
        f"stage: {state.stage_id}  bench: {state.bench_variant}",
        f"component defaults: {get_component_defaults(state.component_defaults).label}",
        (
            f"waveform: {state.pulse_mv:g} mV  {state.pulse_shape}  "
            f"{state.pulse_rate_khz:g} kHz  {state.pulse_width_us:g} µs × "
            f"{state.num_pulses}  duration {state.duration_ms:g} ms"
        ),
    ]
    if state.lf_offset_enabled:
        seed = state.lf_offset_seed if state.lf_offset_seed is not None else "random"
        lines.append(
            f"LF offset: {state.lf_offset_amplitude_mv:g} mV  "
            f"{state.lf_offset_center_hz:g}±{state.lf_offset_span_hz:g} Hz  seed={seed}"
        )
    stage = state.stage()
    if stage.patches_rg or stage.fixed_rg:
        lines.append(
            f"gain: {state.gain:g} V/V  R3 (RG) = {r3_display_for_gain(state.gain)}"
        )
    lines.append(
        f"VREF={state.vref:g} V  VTHRESH={state.vthresh:g} V  VDD={state.vdd:g} V"
    )
    if stage_has_input_network(state.stage_id):
        lines.append(
            f"input network: C2/C3={state.c_couple}  R4/R7={state.r_series}  "
            f"R6/R8={state.r_vref}  R15={state.r_diff}  C4={state.c_diff}"
        )
        if state.electrode_mismatch_pct > 0:
            lines.append(f"electrode mismatch: {state.electrode_mismatch_pct:g} %")
    if stage_has_comparator_network(state.stage_id):
        r5 = f"  R5={state.r_hyst}" if state.stage_id == "03_detector" else ""
        lines.append(f"comparator network: C5={state.c_out}  R9={state.r_comp}{r5}")
    lines.append(f"view: {state.view_mode}")
    return "\n".join(lines)


def parse_ina_gain(value: object, default: int = 2) -> float:
    """Parse integer INA333 gain; minimum 2 V/V for valid RG."""
    gain = parse_int(value, default)
    return float(max(gain, 2))


def resolve_gui_gain(stage_id: str, ina_gain: object, sanity_gain: object) -> float:
    """Pick gain from the visible control for the active stage."""
    stage = get_stage(stage_id or "03_detector")
    if stage.patches_rg:
        return parse_float(sanity_gain, 100.0)
    if stage.fixed_rg:
        return parse_ina_gain(ina_gain, int(default_ina_gain(stage.id)))
    return 2.0


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
