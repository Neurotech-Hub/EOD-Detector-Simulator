"""Comparator output coupling and hysteresis network parameters."""

from __future__ import annotations

from dataclasses import dataclass

COMPARATOR_NETWORK_STAGES = frozenset({"02_frontend", "03_detector"})


@dataclass
class ComparatorNetworkParams:
    """Output filter values as SPICE literals (KiCad EOD_Detector_v3-1 defaults)."""

    c_out: str = "2.2n"
    """Output coupling cap between VREF and ELEC_OUT (board: C5)."""

    r_comp: str = "4.7k"
    """Series resistor from ELEC_OUT to COMP_IN (board: R9)."""

    r_hyst: str = "1Meg"
    """Hysteresis / positive feedback resistor COMP_IN to TRIGGER (board: R5,
    stage 03 only)."""

    def to_spice_params(self) -> dict[str, str]:
        return {
            "C_OUT": self.c_out,
            "R_COMP": self.r_comp,
            "R_HYST": self.r_hyst,
        }


def stage_has_comparator_network(stage_id: str) -> bool:
    """Return whether a stage includes the parameterized output filter network."""
    return stage_id in COMPARATOR_NETWORK_STAGES
