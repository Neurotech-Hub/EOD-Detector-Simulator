"""Parse ngspice raw simulation output."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    extra: dict[str, np.ndarray] = field(default_factory=dict)
    signal_nodes: dict[str, str] = field(default_factory=dict)

    @property
    def vin_diff(self) -> np.ndarray:
        return self.in_p - self.in_n

    def node_voltage(self, node: str) -> np.ndarray:
        """Return voltage trace for a SPICE node name."""
        if node in self.extra:
            return self.extra[node]
        nodes = self.resolved_nodes()
        for key, spice_node in nodes.items():
            if spice_node == node:
                if key == "in_p":
                    return self.in_p
                if key == "in_n":
                    return self.in_n
                if key == "out":
                    return self.out
                if key == "ref":
                    return self.ref
        raise KeyError(f"Node '{node}' not found in simulation result")

    def diff_pair(self, pos_node: str, neg_node: str) -> np.ndarray:
        """Differential voltage between two SPICE nodes."""
        return self.node_voltage(pos_node) - self.node_voltage(neg_node)

    def resolved_nodes(self) -> dict[str, str]:
        if self.signal_nodes:
            return dict(self.signal_nodes)
        return {
            "in_p": "in_p",
            "in_n": "in_n",
            "out": "out",
            "ref": "ref",
        }


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


def _get_trace_optional(raw: RawRead, name: str, length: int) -> np.ndarray:
    """Fetch a trace or return zeros if not saved in the raw file."""
    try:
        return _get_trace(raw, name)
    except KeyError:
        return np.zeros(length)


def load_raw(
    raw_path: Path,
    signal_nodes: dict[str, str] | None = None,
    extra_probes: tuple[str, ...] | None = None,
) -> SimulationResult:
    """Load ngspice raw file and extract probe voltages."""
    raw = RawRead(str(raw_path))
    nodes = signal_nodes or {
        "in_p": "in_p",
        "in_n": "in_n",
        "out": "out",
        "ref": "ref",
    }

    time_s = np.array(raw.get_trace("time").get_wave(0))
    in_p = _get_trace(raw, f"V({nodes['in_p']})")
    in_n = _get_trace(raw, f"V({nodes['in_n']})")
    out = _get_trace(raw, f"V({nodes['out']})")
    ref = _get_trace_optional(raw, f"V({nodes.get('ref', 'ref')})", len(time_s))

    extra: dict[str, np.ndarray] = {}
    seen = set(nodes.values())
    for node in extra_probes or ():
        if node in seen:
            continue
        extra[node] = _get_trace_optional(raw, f"V({node})", len(time_s))
        seen.add(node)

    for logical, spice_node in nodes.items():
        if spice_node in extra or logical in ("in_p", "in_n", "out", "ref"):
            continue
        extra[spice_node] = _get_trace_optional(raw, f"V({spice_node})", len(time_s))

    return SimulationResult(
        time_s=time_s,
        in_p=in_p,
        in_n=in_n,
        out=out,
        ref=ref,
        extra=extra,
        signal_nodes=nodes,
    )
