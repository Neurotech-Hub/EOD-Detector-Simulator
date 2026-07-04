#!/usr/bin/env python3
"""Launch the EOD detector tuning GUI (Plotly Dash)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eod_sim.gui.app import main  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EOD detector tuning GUI")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=8050, help="Port")
    parser.add_argument("--debug", action="store_true", help="Enable Dash debug mode")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    url = f"http://{args.host}:{args.port}"
    print(f"EOD Detector Tuner running at {url}")
    main(project_root=PROJECT_ROOT, host=args.host, port=args.port, debug=args.debug)
