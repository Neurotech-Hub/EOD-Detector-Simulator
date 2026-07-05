"""INA333 symmetric input passive network parameters."""

from __future__ import annotations

from dataclasses import dataclass

INPUT_NETWORK_STAGES = frozenset({"01_passives", "02_frontend", "03_detector"})


@dataclass
class InputNetworkParams:
    """Symmetric INA input network values as SPICE literals (KiCad defaults)."""

    c_couple: str = "4.7n"
    """Input coupling cap (C2, C3) — DC block / HPF with R_SERIES."""

    r_series: str = "100k"
    """Series input resistor (R4, R7)."""

    r_vref: str = "10Meg"
    """VREF bias resistor (R6, R8)."""

    r_diff: str = "1Meg"
    """Differential input resistor between INA+ and INA− (R15)."""

    c_diff: str = "330p"
    """Differential input capacitor between INA+ and INA− (C4)."""

    def to_spice_params(self) -> dict[str, str]:
        return {
            "C_COUPLE": self.c_couple,
            "R_SERIES": self.r_series,
            "R_VREF": self.r_vref,
            "R_DIFF": self.r_diff,
            "C_DIFF": self.c_diff,
        }


def stage_has_input_network(stage_id: str) -> bool:
    """Return whether a stage includes the parameterized input passive network."""
    return stage_id in INPUT_NETWORK_STAGES


def stage_has_ina_gain(stage_id: str) -> bool:
    """Return whether the stage INA333 gain (R3 / RGVAL) is tunable."""
    return stage_id in ("00_sanity_ina333", "02_frontend", "03_detector")
