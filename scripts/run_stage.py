#!/usr/bin/env python3
"""Run a circuit simulation stage: generate waveform -> ngspice -> plot."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eod_sim.input_network import InputNetworkParams, stage_has_input_network  # noqa: E402
from eod_sim.ngspice import NgspiceNotFoundError, NgspiceSimulationError  # noqa: E402
from eod_sim.runner import RunConfig, run_simulation  # noqa: E402
from eod_sim.stages.registry import DEFAULT_STAGE_ID, get_stage, list_stages  # noqa: E402
from eod_sim.waveforms import format_rg_spice, gain_to_rg  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an EOD detector simulation stage")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List registered stages and exit",
    )
    parser.add_argument(
        "--stage",
        default=DEFAULT_STAGE_ID,
        help=f"Stage id (default: {DEFAULT_STAGE_ID})",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Bench variant (e.g. ideal, ti, default). Defaults to stage's default_bench.",
    )
    parser.add_argument("--gain", type=float, default=100.0, help="INA333 gain (V/V)")
    parser.add_argument("--pulse-mv", type=float, default=1.0, help="Peak diff pulse (mV)")
    parser.add_argument(
        "--waveform",
        choices=["square", "rounded"],
        default="square",
        help="EOD pulse shape (default: square for regression tests)",
    )
    parser.add_argument(
        "--pulse-width-us",
        type=float,
        default=200.0,
        help="Total biphasic pulse width for rounded waveform (µs)",
    )
    parser.add_argument("--isi-ms", type=float, default=20.0, help="Inter-pulse interval (ms)")
    parser.add_argument("--num-pulses", type=int, default=4, help="Number of pulses")
    parser.add_argument("--duration-ms", type=float, default=100.0, help="Simulation duration (ms)")
    parser.add_argument(
        "--sample-us",
        type=float,
        default=None,
        help="Waveform + .tran step size (µs). Default: 1 for rounded, 10 for square.",
    )
    parser.add_argument(
        "--pulse-index",
        type=int,
        default=0,
        help="Which pulse to show in the single-pulse zoom plot (0-based)",
    )
    parser.add_argument(
        "--pulse-margin-us",
        type=float,
        default=50.0,
        help="Padding before/after pulse in the zoom plot (µs)",
    )
    parser.add_argument(
        "--no-pulse-zoom",
        action="store_true",
        help="Skip the single-pulse dual-axis zoom plot",
    )
    parser.add_argument(
        "--plot",
        choices=["matplotlib", "plotly"],
        default="matplotlib",
        help="Plot backend",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs",
        help="Root output directory (stage outputs go under outputs/stages/)",
    )
    parser.add_argument("--vref", type=float, default=None, help="Reference voltage (V)")
    parser.add_argument("--vthresh", type=float, default=None, help="Comparator threshold (V)")
    parser.add_argument("--vdd", type=float, default=None, help="Supply voltage (V)")
    parser.add_argument(
        "--lf-offset",
        action="store_true",
        help="Add slow ~20 Hz differential offset (water-recording artifact)",
    )
    parser.add_argument(
        "--lf-offset-mv",
        type=float,
        default=100.0,
        help="Peak LF differential offset amplitude (mV); default 100",
    )
    parser.add_argument(
        "--lf-offset-center-hz",
        type=float,
        default=20.0,
        help="LF offset center frequency (Hz); default 20",
    )
    parser.add_argument(
        "--lf-offset-span-hz",
        type=float,
        default=10.0,
        help="LF offset frequency span ±Hz around center; default 10",
    )
    parser.add_argument(
        "--lf-offset-seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible LF offset f and phase",
    )
    parser.add_argument(
        "--c-couple",
        default=None,
        help="Input coupling cap SPICE value (C2/C3); default 4.7n",
    )
    parser.add_argument(
        "--r-series",
        default=None,
        help="Series input resistor SPICE value (R4/R7); default 100k",
    )
    parser.add_argument(
        "--r-vref",
        default=None,
        help="VREF bias resistor SPICE value (R6/R8); default 10Meg",
    )
    parser.add_argument(
        "--r-diff",
        default=None,
        help="Differential input resistor SPICE value (R15); default 1Meg",
    )
    parser.add_argument(
        "--c-diff",
        default=None,
        help="Differential input cap SPICE value (C4); default 330p",
    )
    return parser.parse_args()


def _input_network_from_args(args: argparse.Namespace) -> InputNetworkParams:
    net = InputNetworkParams()
    if args.c_couple is not None:
        net.c_couple = args.c_couple
    if args.r_series is not None:
        net.r_series = args.r_series
    if args.r_vref is not None:
        net.r_vref = args.r_vref
    if args.r_diff is not None:
        net.r_diff = args.r_diff
    if args.c_diff is not None:
        net.c_diff = args.c_diff
    return net


def print_stage_list() -> None:
    for stage in list_stages():
        flag = "active" if stage.is_runnable else stage.status
        variants = ", ".join(stage.benches) if stage.benches else "—"
        print(f"{stage.id:22} [{flag:7}] {stage.title}")
        print(f"{'':22}          {stage.description}")
        if stage.benches:
            print(f"{'':22}          benches: {variants}")


def main() -> int:
    args = parse_args()

    if args.list:
        print_stage_list()
        return 0

    try:
        stage = get_stage(args.stage)
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    bench_variant = args.model or stage.default_bench
    print(f"Stage: {args.stage}")
    print(f"Bench: {bench_variant}")

    if stage.patches_rg:
        rg_spice = format_rg_spice(gain_to_rg(args.gain))
        print(f"Gain: {args.gain:.1f} V/V  ->  RG = {rg_spice}")

    if stage.fixed_rg:
        print("INA333 gain: 2 V/V (RG = 100k, fixed in schematic)")

    if stage.supports_eod_input:
        print(f"Waveform: {args.waveform}", end="")
        if args.waveform == "rounded":
            print(f"  ({args.pulse_width_us:.0f} µs biphasic width)")
        else:
            print()

    if stage_has_input_network(args.stage):
        net = _input_network_from_args(args)
        print(
            "Input network: "
            f"C_COUPLE={net.c_couple}  R_SERIES={net.r_series}  "
            f"R_VREF={net.r_vref}  R_DIFF={net.r_diff}  C_DIFF={net.c_diff}"
        )

    config = RunConfig(
        stage_id=args.stage,
        bench_variant=bench_variant,
        gain=args.gain,
        pulse_mv=args.pulse_mv,
        pulse_shape=args.waveform,
        pulse_width_us=args.pulse_width_us,
        isi_ms=args.isi_ms,
        num_pulses=args.num_pulses,
        duration_ms=args.duration_ms,
        sample_us=args.sample_us,
        pulse_index=args.pulse_index,
        pulse_margin_us=args.pulse_margin_us,
        pulse_zoom=not args.no_pulse_zoom,
        plot_backend=args.plot,
        output_root=args.output_dir,
        vref=args.vref,
        vthresh=args.vthresh,
        vdd=args.vdd,
        lf_offset_enabled=args.lf_offset,
        lf_offset_amplitude_mv=args.lf_offset_mv,
        lf_offset_center_hz=args.lf_offset_center_hz,
        lf_offset_span_hz=args.lf_offset_span_hz,
        lf_offset_seed=args.lf_offset_seed,
        input_network=_input_network_from_args(args),
    )

    try:
        result = run_simulation(config, PROJECT_ROOT)
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except NgspiceNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except NgspiceSimulationError as exc:
        log_path = config.output_root / "stages" / args.stage / f"ngspice_{bench_variant}.log"
        print(f"Error: {exc}", file=sys.stderr)
        print(f"See log: {log_path}", file=sys.stderr)
        return 1

    print(f"Output dir: {result.output_dir}")
    print(f"Simulation raw: {result.raw_path}")
    print(f"Plot saved: {result.plot_path}")
    if result.pulse_plot_path is not None:
        print(f"Pulse zoom: {result.pulse_plot_path}")

    if result.peak_vin_mv is not None:
        print(f"Peak Vin_diff: {result.peak_vin_mv:.3f} mV")
    if result.lf_offset is not None:
        phase_deg = math.degrees(result.lf_offset.phase_rad)
        print(
            f"LF offset: {result.lf_offset.frequency_hz:.2f} Hz, "
            f"phase {phase_deg:.1f}°, {result.lf_offset.amplitude_mv:g} mV"
        )
    if stage.patches_rg and result.measured_gain is not None:
        peak_vout_mv = result.measured_gain * result.peak_vin_mv
        print(f"Peak Vout (rel REF): {peak_vout_mv:.3f} mV")
        print(f"Measured gain: {result.measured_gain:.1f} V/V")
    elif stage.id in ("02_frontend", "03_detector") and result.measured_gain is not None:
        peak_vout_mv = result.measured_gain * result.peak_vin_mv
        print(f"Peak ELEC_OUT (rel VREF): {peak_vout_mv:.3f} mV")
        print(f"Measured gain: {result.measured_gain:.1f} V/V")
    elif stage.comparator_stage and result.vout_min_v is not None and result.peak_vout_v is not None:
        print(f"Vout low: {result.vout_min_v:.3f} V")
        print(f"Vout high: {result.peak_vout_v:.3f} V")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
