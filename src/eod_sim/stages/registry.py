"""Circuit stage registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

StageStatus = Literal["active", "planned"]
DriveMode = Literal["diff_inputs", "electrodes"]
OverviewBottomMode = Literal["absolute", "diff", "relative"]


@dataclass(frozen=True)
class Stage:
    """Metadata for one simulation stage."""

    id: str
    title: str
    description: str
    status: StageStatus
    benches: dict[str, str]
    supports_eod_input: bool = True
    default_bench: str = "ideal"
    patches_rg: bool = False
    drive_mode: DriveMode = "diff_inputs"
    default_vcm: float = 2.5
    default_vref: float = 1.65
    default_vthresh: float = 1.85
    default_vdd: float = 3.3
    fixed_rg: bool = False
    signal_nodes: dict[str, str] = field(default_factory=dict)
    extra_probes: tuple[str, ...] = ()
    overview_input: tuple[str, str] = ("in_p", "in_n")
    overview_output: str | tuple[str, str] = "out"
    overview_bottom_mode: OverviewBottomMode = "absolute"
    pulse_zoom_left: tuple[str, str] | None = None
    pulse_zoom_right: str | tuple[str, str] = "out"
    pulse_zoom_right_mode: OverviewBottomMode = "relative"
    input_label: str = "Differential Input"
    output_label: str | None = None
    comparator_stage: bool = False

    @property
    def is_runnable(self) -> bool:
        return self.status == "active" and bool(self.benches)

    def stage_dir(self, circuits_dir: Path) -> Path:
        return circuits_dir / "stages" / self.id

    def bench_path(self, circuits_dir: Path, bench_variant: str) -> Path:
        if bench_variant not in self.benches:
            raise KeyError(
                f"Stage '{self.id}' has no bench for variant '{bench_variant}'. "
                f"Available: {', '.join(self.benches)}"
            )
        return self.stage_dir(circuits_dir) / self.benches[bench_variant]

    def output_dir(self, base_output_dir: Path) -> Path:
        return base_output_dir / "stages" / self.id

    def resolved_signal_nodes(self) -> dict[str, str]:
        """Return signal node map with defaults for sanity stages."""
        if self.signal_nodes:
            return dict(self.signal_nodes)
        return {
            "in_p": "in_p",
            "in_n": "in_n",
            "out": "out",
            "ref": "ref",
        }

    def save_nodes(self) -> list[str]:
        """SPICE nodes to save in .save directive."""
        nodes = set(self.resolved_signal_nodes().values())
        nodes.update(self.extra_probes)
        return sorted(nodes)

    def driven_nodes(self) -> tuple[str, str]:
        """SPICE node pair driven directly by the stimulus filesource."""
        if self.drive_mode == "electrodes":
            return ("elec_a", "elec_b")
        nodes = self.resolved_signal_nodes()
        return (nodes["in_p"], nodes["in_n"])


EOD_SIGNAL_NODES = {
    "elec_a": "elec_a",
    "elec_b": "elec_b",
    "ina_p": "ina_p",
    "ina_n": "ina_n",
    "elec_out": "elec_out",
    "comp_in": "comp_in",
    "trigger": "trigger",
    "thresh": "thresh",
    "vref": "vref",
    "in_p": "ina_p",
    "in_n": "ina_n",
    "out": "elec_out",
    "ref": "vref",
}


STAGES: tuple[Stage, ...] = (
    Stage(
        id="00_sanity_ina333",
        title="INA333 sanity check",
        description="INA333 only with EOD pulse input; regression baseline.",
        status="active",
        benches={"ideal": "bench_ideal.cir", "ti": "bench_ti.cir"},
        default_bench="ti",
        patches_rg=True,
        drive_mode="diff_inputs",
        default_vcm=2.5,
    ),
    Stage(
        id="00_sanity_mcp6561",
        title="MCP6561 sanity check",
        description="Comparator threshold step; low below Vref, high above Vref.",
        status="active",
        benches={"default": "bench.cir"},
        supports_eod_input=False,
        default_bench="default",
        default_vdd=5.0,
        default_vref=2.5,
        comparator_stage=True,
    ),
    Stage(
        id="01_passives",
        title="Input passives",
        description="Electrode coupling, bias, and differential network to INA inputs.",
        status="active",
        benches={"default": "bench.cir"},
        default_bench="default",
        drive_mode="electrodes",
        default_vcm=0.0,
        default_vref=1.65,
        default_vdd=3.3,
        signal_nodes={
            "elec_a": "elec_a",
            "elec_b": "elec_b",
            "ina_p": "ina_p",
            "ina_n": "ina_n",
            "in_p": "ina_p",
            "in_n": "ina_n",
            "out": "ina_p",
            "ref": "vref",
        },
        extra_probes=("elec_a", "elec_b"),
        overview_input=("elec_a", "elec_b"),
        overview_output=("ina_p", "ina_n"),
        overview_bottom_mode="diff",
        pulse_zoom_left=("elec_a", "elec_b"),
        pulse_zoom_right=("ina_p", "ina_n"),
        pulse_zoom_right_mode="diff",
        input_label="Electrode differential (ELEC_A − ELEC_B)",
        output_label="INA input differential (INA+ − INA−)",
    ),
    Stage(
        id="02_frontend",
        title="INA333 front-end",
        description="Passives + INA333 (G=2) and output coupling to comparator input.",
        status="active",
        benches={"ideal": "bench_ideal.cir", "ti": "bench_ti.cir"},
        default_bench="ti",
        drive_mode="electrodes",
        default_vcm=0.0,
        default_vref=1.65,
        default_vdd=3.3,
        fixed_rg=True,
        # No comparator in stage 02: trigger/thresh nodes do not exist.
        signal_nodes={
            k: v for k, v in EOD_SIGNAL_NODES.items() if k not in ("trigger", "thresh")
        },
        extra_probes=("elec_a", "elec_b", "comp_in"),
        overview_input=("ina_p", "ina_n"),
        overview_output="elec_out",
        overview_bottom_mode="absolute",
        pulse_zoom_left=("ina_p", "ina_n"),
        pulse_zoom_right="elec_out",
        pulse_zoom_right_mode="relative",
        input_label="INA differential input",
        output_label="ELEC_OUT",
    ),
    Stage(
        id="03_detector",
        title="Full detector",
        description="Complete front-end with MCP6561 comparator and fixed threshold.",
        status="active",
        benches={"ideal": "bench_ideal.cir", "ti": "bench_ti.cir"},
        default_bench="ti",
        drive_mode="electrodes",
        default_vcm=0.0,
        default_vref=1.65,
        default_vthresh=1.85,
        default_vdd=3.3,
        fixed_rg=True,
        signal_nodes={
            **EOD_SIGNAL_NODES,
            "out": "trigger",
            "ref": "vref",
        },
        extra_probes=("elec_a", "elec_b", "elec_out", "comp_in", "thresh", "trigger"),
        overview_input=("ina_p", "ina_n"),
        overview_output="trigger",
        overview_bottom_mode="absolute",
        pulse_zoom_left=("ina_p", "ina_n"),
        pulse_zoom_right="elec_out",
        pulse_zoom_right_mode="relative",
        input_label="INA differential input",
        output_label="Comparator output",
        comparator_stage=True,
    ),
)

STAGE_BY_ID: dict[str, Stage] = {stage.id: stage for stage in STAGES}

DEFAULT_STAGE_ID = "00_sanity_ina333"


def get_stage(stage_id: str) -> Stage:
    """Return a stage by id or raise KeyError."""
    try:
        return STAGE_BY_ID[stage_id]
    except KeyError as exc:
        known = ", ".join(STAGE_BY_ID)
        raise KeyError(f"Unknown stage '{stage_id}'. Known stages: {known}") from exc


def list_stages() -> list[Stage]:
    """Return all registered stages in progression order."""
    return list(STAGES)
