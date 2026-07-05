# Electrodes — notes for sim and bench

Context: fine **silver wire**, ~**5 mm exposed** to water, ~**1 cm** from PCB,
**fresh water** (~50–500 µS/cm). Fixed v3-1 topology; value changes only unless
noted.

## Bare Ag in freshwater (current)

Each electrode behaves roughly like a **Randles cell**:

| Element | Order of magnitude | Relevance at EOD rates (200–1000 µs) |
|---------|-------------------|--------------------------------------|
| **Rs** (spreading) | ~3–30 kΩ per wire (~15 kΩ nominal at ~100 µS/cm) | **Dominant** — each electrode ≈ a resistor in-band |
| **Cdl** (double layer) | ~0.5–1 µF | ~200 Ω at ~1 kHz — negligible vs 4.7 nF coupling (C2/C3) |
| **Rct** (charge transfer) | Very high (bare Ag, no stable couple) | Interface drifts; slow polarization |
| **Drift / offset** | Unstable half-cell, mV-scale wander over seconds–minutes | Prime suspect for **LF bleed-through** and **continuous triggering** |

**Rs sits in series with C4 (330 pF)** on the differential path → extra LPF corner
~Rs/(2·C4) ≈ **~16 kHz** with ~30 kΩ total Rs. Compounds the in-band C4 roll-off
already flagged in the README (C4 → **47 pF** recommendation still applies).

**What does *not* matter much:** INA bias current × Rs (~µV); Cdl on the HPF
(dominated by C2/C3).

## What actually drives field failures (bare or chlorided)

1. **Electrode + board mismatch → CM→DM conversion** — unequal Rs/Cdl/Rct, plus
   C2/C3 and R4/R7 tolerance. Tank gradients and mains couple in as
   **common-mode**; even 0.1–1% conversion can produce mV differential at the
   INA — enough to cross threshold intermittently.
2. **Slow drift / DC offset** — large for **bare Ag**; much smaller for **matched
   Ag/AgCl**.

**Now live in the sim:** the stimulus
(`circuits/stages/includes/eod_stimulus.inc`) drives stiff SRC_A/SRC_B
nodes through per-electrode series resistors `R_ELEC_A/B`. The
`--electrode-mismatch <pct>` flag (GUI: **Electrode mismatch (%)**) sets
Rs = **15 kΩ ± m/2** per electrode (0 = stiff drive, model off). This
captures the **resistive** effects above — in-band droop through C4 and
one-sided lobe skew from unequal Rs. Cdl/Rct, drift, and common-mode
pickup are still not represented (see below).

## Ag/AgCl wires — what changes

| | Bare Ag | Ag/AgCl |
|---|---------|---------|
| **Rct** | Very high | ~1–20 kΩ (reversible AgCl/Ag couple) |
| **Drift / polarization** | Large, unstable | Small stable half-cell (~tens of mV) |
| **Rs, Cdl** | Same (geometry + water) | Same |
| **Mismatch CM→DM** | Yes | **Still yes** — unequal chloriding, area, Rct; board tolerance unchanged |

Ag/AgCl removes the main **drift** failure mode but **not** mismatch or CM→DM.
Residual risk: **differential DC offset** between wires (tens of mV) eating
trigger margin (threshold ~200 mV above VREF at G≈3).

**Wearable caveat:** small chlorided wires **deplete AgCl** under sustained
DC/bias; behavior can revert toward bare Ag over long immersion — bench soak
test, not SPICE.

## Simulation — worth it or not?

- **Not worth chasing exact Rs/Cdl/Rct** — water chemistry and wire prep dominate
  uncertainty.
- **Worth one bounded pass:** mismatch × common-mode **margin** sweep, not “find
  the true Rs.”

**Done (first slice):** per-electrode series **Rs with mismatch %**
(`--electrode-mismatch`) is implemented — see README "Electrode impedance
mismatch."

Remaining for a future pass:

- Replace the differential-only source with **CM source + differential
  (fish) source** and extend each electrode to the full **Rs ∥ (Cdl +
  Rct)** Randles branch with **mismatch %** on Cdl/Rct too.
- **Bare Ag:** include slow drift source (mV, <1 Hz).
- **Ag/AgCl:** low Rct (~5 kΩ), **no large drift**; add small **Vhalf offset
  mismatch** (±25 mV swept).
- Sweep: mismatch 0–50%, CM amplitude; watch INA diff, COMP_IN, TRIGGER for
  false edges.

Output = **tolerance budget**, not a single “correct” electrode value.

## Practical recommendation

1. **Bench:** prefer **Ag/AgCl** (or chlorided silver) for stable LF behavior vs
   bare Ag in plain water.
2. **Component tuning:** proceed with README suggestions (**C4 = 47 pF**, **R3 →
   G≈3**, keep R5/R9/C5) — valid regardless of electrode chemistry for Rs.
3. **Sim next (optional but targeted):** one Ag/AgCl-oriented mismatch + CM sweep
   to confirm margin before long tank tests; skip full bare-Ag drift modeling if
   electrodes are chlorided.

See also: [README](README.md) (board map, suggested values, deferred modeling).
