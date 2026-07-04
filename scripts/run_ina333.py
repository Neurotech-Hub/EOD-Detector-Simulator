#!/usr/bin/env python3
"""Run INA333 EOD pulse simulation: generate waveform -> ngspice -> plot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eod_sim.ngspice import (  # noqa: E402
    NgspiceNotFoundError,
    NgspiceSimulationError,
    bench_template_path,
    run_batch,
    write_patched_netlist,
)
from eod_sim.plot import plot_waveforms  # noqa: E402
from eod_sim.results import load_raw  # noqa: E402
from eod_sim.waveforms import (  # noqa: E402
    EODPulseConfig,
    format_rg_spice,
    gain_to_rg,
    generate_and_write_pwl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate INA333 with EOD-like input")
    parser.add_argument(
        "--model",
        choices=["ideal", "ti"],
        default="ideal",
        help="INA333 model: ideal 3-op-amp or TI vendor macromodel",
    )
    parser.add_argument("--gain", type=float, default=100.0, help="INA333 gain (V/V)")
    parser.add_argument("--pulse-mv", type=float, default=1.0, help="Peak diff pulse (mV)")
    parser.add_argument("--isi-ms", type=float, default=20.0, help="Inter-pulse interval (ms)")
    parser.add_argument("--num-pulses", type=int, default=4, help="Number of pulses")
    parser.add_argument("--duration-ms", type=float, default=100.0, help="Simulation duration (ms)")
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
        help="Output directory for waveform, raw, and plot files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    circuits_dir = PROJECT_ROOT / "circuits"

    rg_ohms = gain_to_rg(args.gain)
    rg_spice = format_rg_spice(rg_ohms)

    print(f"Model: {args.model}")
    print(f"Gain: {args.gain:.1f} V/V  ->  RG = {rg_spice}")

    config = EODPulseConfig(
        pulse_mv=args.pulse_mv,
        isi_ms=args.isi_ms,
        num_pulses=args.num_pulses,
        duration_ms=args.duration_ms,
    )
    wf = generate_and_write_pwl(output_dir, config)
    print(f"Wrote waveform file: {wf.diff_path.name}")

    netlist_template = bench_template_path(circuits_dir, args.model)
    netlist_run = output_dir / f"ina333_bench_{args.model}_run.cir"
    write_patched_netlist(
        netlist_template,
        netlist_run,
        rg_spice,
        project_root=PROJECT_ROOT,
        model=args.model,
    )

    raw_path = output_dir / f"simulation_{args.model}.raw"
    log_path = output_dir / f"ngspice_{args.model}.log"

    try:
        run_batch(netlist_run, raw_path, log_path=log_path)
    except NgspiceNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except NgspiceSimulationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(f"See log: {log_path}", file=sys.stderr)
        return 1

    print(f"Simulation raw: {raw_path}")

    result = load_raw(raw_path)
    plot_path = plot_waveforms(
        result,
        output_dir,
        args.gain,
        backend=args.plot,
        model=args.model,
    )
    print(f"Plot saved: {plot_path}")

    peak_vin_mv = float(result.vin_diff.max() * 1e3)
    peak_vout_mv = float((result.out - result.ref).max() * 1e3)
    print(f"Peak Vin_diff: {peak_vin_mv:.3f} mV")
    print(f"Peak Vout (rel REF): {peak_vout_mv:.3f} mV")
    if peak_vin_mv > 0:
        print(f"Measured gain: {peak_vout_mv / peak_vin_mv:.1f} V/V")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
