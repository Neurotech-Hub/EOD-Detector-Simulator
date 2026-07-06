#!/usr/bin/env python3
"""Inspect a recorded EOD CSV: baseline removal, window selection, normalization."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eod_sim.recorded_pulse import (  # noqa: E402
    DEFAULT_RECORDED_ID,
    DEFAULT_SAMPLE_RATE_HZ,
    get_recorded_template,
    get_recorded_template_from_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv",
        nargs="?",
        type=Path,
        help="CSV path (mV samples). Omit to use bundled default.",
    )
    parser.add_argument(
        "--sample-rate-hz",
        type=float,
        default=DEFAULT_SAMPLE_RATE_HZ,
        help=f"Sample rate (default: {DEFAULT_SAMPLE_RATE_HZ:g})",
    )
    parser.add_argument(
        "--source-id",
        default=DEFAULT_RECORDED_ID,
        help="Bundled source id when csv is omitted",
    )
    args = parser.parse_args()

    if args.csv is None:
        tpl = get_recorded_template(args.source_id)
    else:
        tpl = get_recorded_template_from_path(args.csv, sample_rate_hz=args.sample_rate_hz)

    print(f"Source:        {tpl.source_id}")
    print(f"Baseline:      {tpl.baseline_mv:+.3f} mV")
    print(f"Raw peak:      {tpl.raw_peak_mv:.3f} mV")
    print(f"Window idx:    {tpl.window_start_idx}..{tpl.window_end_idx}")
    print(f"Duration:      {tpl.duration_us:.1f} µs")
    print(f"Sample rate:   {tpl.sample_rate_hz:g} Hz ({tpl.native_sample_us:.3f} µs)")
    print(f"Samples:       {len(tpl.time_s)}")
    print(f"Norm peak:     {max(abs(tpl.shape.min()), abs(tpl.shape.max())):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
