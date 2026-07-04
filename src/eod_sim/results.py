"""Parse ngspice raw simulation output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PyLTSpice.raw.raw_read import RawRead


@dataclass
class SimulationResult:
    """Parsed transient simulation waveforms."""

    time_s: np.ndarray
    in_p: np.ndarray
    in_n: np.ndarray
    out: np.ndarray
    ref: np.ndarray

    @property
    def vin_diff(self) -> np.ndarray:
        return self.in_p - self.in_n


def _get_trace(raw: RawRead, name: str) -> np.ndarray:
    """Fetch a trace by name, trying common ngspice naming variants."""
    candidates = [name, name.lower(), name.upper()]
    for candidate in candidates:
        try:
            return np.array(raw.get_trace(candidate).get_wave(0))
        except (IndexError, AttributeError, KeyError, TypeError):
            continue
    available = [str(t) for t in raw.get_trace_names()]
    raise KeyError(f"Trace '{name}' not found. Available: {available}")


def load_raw(raw_path: Path) -> SimulationResult:
    """Load ngspice raw file and extract probe voltages."""
    raw = RawRead(str(raw_path))

    time_s = np.array(raw.get_trace("time").get_wave(0))
    in_p = _get_trace(raw, "V(in_p)")
    in_n = _get_trace(raw, "V(in_n)")
    out = _get_trace(raw, "V(out)")
    ref = _get_trace(raw, "V(ref)")

    return SimulationResult(
        time_s=time_s,
        in_p=in_p,
        in_n=in_n,
        out=out,
        ref=ref,
    )
