#!/usr/bin/env python3
"""Run INA333 sanity stage (alias for run_stage.py --stage 00_sanity_ina333)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

if __name__ == "__main__":
    if not any(arg in sys.argv for arg in ("--stage", "--list", "-h", "--help")):
        sys.argv[1:1] = ["--stage", "00_sanity_ina333"]

    from run_stage import main

    raise SystemExit(main())
