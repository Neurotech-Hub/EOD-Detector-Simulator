"""INA333 symmetric input passive network parameters."""

from __future__ import annotations

from dataclasses import dataclass

INPUT_NETWORK_STAGES = frozenset({"01_passives", "02_frontend", "03_detector"})

ELECTRODE_RS_OHMS = 15e3
"""Nominal per-electrode spreading resistance when the electrode model is
enabled (fine Ag wire, ~5 mm exposed, ~100 µS/cm fresh water). See
ELECTRODES.md."""

_ELECTRODE_OFF = "1m"
"""1 mΩ — electrically identical to a stiff drive (electrode model off)."""


def _format_ohms(value: float) -> str:
    """Format a resistance in ohms as a SPICE literal."""
    return f"{value:.6g}"


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

    c_diff: str = "47p"
    """Differential input capacitor between INA+ and INA− (C4)."""

    electrode_mismatch_pct: float = 0.0
    """Electrode impedance mismatch (%). 0 disables the electrode model
    (stiff drive). >0 inserts Rs = 15 kΩ ± m/2 per electrode between the
    source and ELEC_A/ELEC_B. See ELECTRODES.md."""

    @property
    def electrode_model_enabled(self) -> bool:
        return self.electrode_mismatch_pct > 0.0

    def electrode_resistances(self) -> tuple[str, str]:
        """SPICE literals for (R_ELEC_A, R_ELEC_B)."""
        if not self.electrode_model_enabled:
            return (_ELECTRODE_OFF, _ELECTRODE_OFF)
        delta = ELECTRODE_RS_OHMS * self.electrode_mismatch_pct / 200.0
        return (
            _format_ohms(ELECTRODE_RS_OHMS + delta),
            _format_ohms(ELECTRODE_RS_OHMS - delta),
        )

    def to_spice_params(self) -> dict[str, str]:
        r_elec_a, r_elec_b = self.electrode_resistances()
        return {
            "C_COUPLE": self.c_couple,
            "R_SERIES": self.r_series,
            "R_VREF": self.r_vref,
            "R_DIFF": self.r_diff,
            "C_DIFF": self.c_diff,
            "R_ELEC_A": r_elec_a,
            "R_ELEC_B": r_elec_b,
        }


def stage_has_input_network(stage_id: str) -> bool:
    """Return whether a stage includes the parameterized input passive network."""
    return stage_id in INPUT_NETWORK_STAGES


def stage_has_ina_gain(stage_id: str) -> bool:
    """Return whether the stage INA333 gain (R3 / RGVAL) is tunable."""
    return stage_id in ("00_sanity_ina333", "02_frontend", "03_detector")
