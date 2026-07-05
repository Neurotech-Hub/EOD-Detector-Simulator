"""Shared simulation runner for circuit stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eod_sim.comparator_network import ComparatorNetworkParams, stage_has_comparator_network
from eod_sim.input_network import InputNetworkParams, stage_has_input_network
from eod_sim.ngspice import bench_template_path, run_batch, write_patched_netlist
from eod_sim.plot import PulseViewConfig, plot_single_pulse, plot_waveforms
from eod_sim.results import SimulationResult, load_raw
from eod_sim.stages.registry import DEFAULT_STAGE_ID, Stage, get_stage
from eod_sim.validation import (
    SimulationQuality,
    SimulationValidationError,
    validate_simulation,
)
from eod_sim.waveforms import (
    EODPulseConfig,
    LFOffsetParams,
    default_sample_us,
    format_duration_spice,
    format_rg_spice,
    format_timestep_spice,
    gain_to_rg,
    generate_and_write_pwl,
)


@dataclass
class RunConfig:
    stage_id: str = DEFAULT_STAGE_ID
    bench_variant: str | None = None
    gain: float = 100.0
    pulse_mv: float = 1.0
    pulse_shape: str = "square"
    pulse_width_us: float = 200.0
    isi_ms: float = 20.0
    num_pulses: int = 4
    duration_ms: float = 100.0
    sample_us: float | None = None
    pulse_index: int = 0
    pulse_margin_us: float | None = None
    pulse_zoom: bool = True
    plot_backend: str = "matplotlib"
    output_root: Path | None = None
    vref: float | None = None
    vthresh: float | None = None
    vdd: float | None = None
    lf_offset_enabled: bool = False
    lf_offset_amplitude_mv: float = 100.0
    lf_offset_center_hz: float = 20.0
    lf_offset_span_hz: float = 10.0
    lf_offset_seed: int | None = None
    input_network: InputNetworkParams | None = None
    comparator_network: ComparatorNetworkParams | None = None


@dataclass
class RunResult:
    stage: Stage
    bench_variant: str
    output_dir: Path
    raw_path: Path
    plot_path: Path
    pulse_plot_path: Path | None
    peak_vin_mv: float | None
    peak_vout_v: float | None
    vout_min_v: float | None
    measured_gain: float | None
    simulation: SimulationResult | None = None
    lf_offset: LFOffsetParams | None = None
    quality: SimulationQuality | None = None


def _measured_gain(stage: Stage, result: SimulationResult) -> float | None:
    nodes = stage.resolved_signal_nodes()
    ina_diff = result.diff_pair(
        nodes["in_p"],
        nodes["in_n"],
    )
    peak_vin_mv = float(ina_diff.max() * 1e3)
    if peak_vin_mv <= 0:
        return None

    if stage.id in ("02_frontend", "03_detector"):
        elec_out = result.node_voltage(nodes["elec_out"])
        ref = result.node_voltage(nodes["ref"])
        peak_vout_mv = float((elec_out - ref).max() * 1e3)
        return peak_vout_mv / peak_vin_mv

    if stage.patches_rg:
        peak_vout_mv = float((result.out - result.ref).max() * 1e3)
        return peak_vout_mv / peak_vin_mv

    return None


def run_simulation(
    config: RunConfig,
    project_root: Path,
) -> RunResult:
    """Generate waveform, run ngspice, and plot results for a stage."""
    stage = get_stage(config.stage_id)
    if not stage.is_runnable:
        raise ValueError(
            f"Stage '{stage.id}' is not runnable (status={stage.status}). "
            "Implement netlists and set status='active' in the registry."
        )

    bench_variant = config.bench_variant or stage.default_bench
    circuits_dir = project_root / "circuits"
    output_root = (config.output_root or project_root / "outputs").resolve()
    output_dir = stage.output_dir(output_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    params: dict[str, str] = {
        "VDD": f"{config.vdd if config.vdd is not None else stage.default_vdd:g}",
        "VREF": f"{config.vref if config.vref is not None else stage.default_vref:g}",
        "TSTOP": format_duration_spice(config.duration_ms),
    }
    if stage.comparator_stage and stage.id != "00_sanity_mcp6561":
        params["VTHRESH"] = (
            f"{config.vthresh if config.vthresh is not None else stage.default_vthresh:g}"
        )
    if stage.patches_rg or stage.fixed_rg:
        params["RGVAL"] = format_rg_spice(gain_to_rg(config.gain))

    sample_us = (
        config.sample_us
        if config.sample_us is not None
        else default_sample_us(config.pulse_shape)
    )
    params["TSTEP"] = format_timestep_spice(sample_us)

    if stage_has_input_network(stage.id):
        net = config.input_network or InputNetworkParams()
        params.update(net.to_spice_params())

    comp: ComparatorNetworkParams | None = None
    if stage_has_comparator_network(stage.id):
        comp = config.comparator_network or ComparatorNetworkParams()
        params.update(comp.to_spice_params())

    wf_config: EODPulseConfig | None = None
    wf_result = None
    lf_offset: LFOffsetParams | None = None
    if stage.supports_eod_input:
        wf_config = EODPulseConfig(
            pulse_mv=config.pulse_mv,
            pulse_shape=config.pulse_shape,
            pulse_width_us=config.pulse_width_us,
            isi_ms=config.isi_ms,
            num_pulses=config.num_pulses,
            duration_ms=config.duration_ms,
            sample_us=sample_us,
            drive_mode=stage.drive_mode,
            vcm=stage.default_vcm,
            lf_offset_enabled=config.lf_offset_enabled,
            lf_offset_amplitude_mv=config.lf_offset_amplitude_mv,
            lf_offset_center_hz=config.lf_offset_center_hz,
            lf_offset_span_hz=config.lf_offset_span_hz,
            lf_offset_seed=config.lf_offset_seed,
        )
        wf_result = generate_and_write_pwl(output_dir, wf_config)
        lf_offset = wf_result.lf_offset

    template_path = bench_template_path(circuits_dir, stage, bench_variant)
    netlist_run = output_dir / f"bench_{bench_variant}_run.cir"
    write_patched_netlist(
        template_path,
        netlist_run,
        stage,
        params=params or None,
    )

    raw_path = output_dir / f"simulation_{bench_variant}.raw"
    log_path = output_dir / f"ngspice_{bench_variant}.log"
    run_batch(netlist_run, raw_path, log_path=log_path)

    signal_nodes = stage.resolved_signal_nodes()
    result = load_raw(
        raw_path,
        signal_nodes=signal_nodes if stage.signal_nodes else None,
        extra_probes=stage.extra_probes,
    )

    quality = validate_simulation(
        result,
        stage=stage,
        tstop_s=config.duration_ms * 1e-3,
        waveform=wf_result,
    )
    if not quality.passed:
        raise SimulationValidationError(
            "Simulation failed validation:\n- "
            + "\n- ".join(quality.errors)
            + f"\nSee log: {log_path}"
        )

    measured_gain = _measured_gain(stage, result)
    plot_gain = measured_gain if stage.patches_rg or stage.id in ("02_frontend", "03_detector") else None

    stimulus = (wf_result.time_s, wf_result.vin_diff) if wf_result is not None else None

    plot_path = plot_waveforms(
        result,
        output_dir,
        stage=stage,
        gain=plot_gain,
        backend=config.plot_backend,
        bench_variant=bench_variant,
        stimulus=stimulus,
    )

    pulse_plot_path = None
    if stage.supports_eod_input and config.pulse_zoom and wf_config is not None:
        if config.pulse_margin_us is not None:
            t_start, t_end = wf_config.pulse_view_window_s(
                pulse_index=config.pulse_index,
                margin_us=config.pulse_margin_us,
            )
        else:
            t_start, t_end = wf_config.pulse_view_window_s(
                pulse_index=config.pulse_index,
            )
        view = PulseViewConfig(
            pulse_onset_s=wf_config.pulse_onset_s(config.pulse_index),
            t_start_s=t_start,
            t_end_s=t_end,
            pulse_index=config.pulse_index,
        )
        pulse_plot_path = plot_single_pulse(
            result,
            output_dir,
            view,
            stage=stage,
            gain=plot_gain,
            backend=config.plot_backend,
            bench_variant=bench_variant,
            stimulus=stimulus,
        )

    nodes = stage.resolved_signal_nodes()
    if stage.supports_eod_input and stage.signal_nodes:
        ina_diff = result.diff_pair(nodes["in_p"], nodes["in_n"])
        peak_vin_mv = float(ina_diff.max() * 1e3) if len(ina_diff) else None
    else:
        peak_vin_mv = float(result.vin_diff.max() * 1e3) if len(result.vin_diff) else None

    peak_vout_v = float(result.out.max()) if len(result.out) else None
    vout_min_v = float(result.out.min()) if len(result.out) else None

    return RunResult(
        stage=stage,
        bench_variant=bench_variant,
        output_dir=output_dir,
        raw_path=raw_path,
        plot_path=plot_path,
        pulse_plot_path=pulse_plot_path,
        peak_vin_mv=peak_vin_mv,
        peak_vout_v=peak_vout_v,
        vout_min_v=vout_min_v,
        measured_gain=measured_gain,
        simulation=result,
        lf_offset=lf_offset,
        quality=quality,
    )
