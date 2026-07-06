# FUTURE — project intent, hardware review, and where to take it

A knowledge-capture document for the EOD Detector (v3-1): why it exists,
how the current hardware works part-by-part, what this simulation/bench
campaign taught us, and what would make the circuit more robust — biased
strongly toward **zero-or-minor changes to the existing PCB**.

See also: [README](README.md) (board map, suggested values),
[C4_STABILITY.md](C4_STABILITY.md) (oscillation sweep),
[ELECTRODES.md](ELECTRODES.md) (electrode physics).

## 1. Project intent

Detect the electric organ discharges (EODs) of weakly electric fish in
fresh water and emit a clean digital TRIGGER (plus LED indication) per
pulse. The device is a **battery-powered wearable**: fine silver wire
electrodes (~5 mm exposed, ~1 cm from the PCB) pick up the fish's
biphasic field pulses — roughly 100 µV to hundreds of mV differential,
200–1000 µs wide, at rates up to ~1 kHz — in an electrically hostile
environment (electrode drift, tank gradients, mains pickup).

The design constraints that shaped everything:

- **Micropower.** Every active part is chosen for µA-class quiescent
  current (INA333 ≈ 25 µA, MCP6561 ≈ 100 µA, OPA333 ≈ 17 µA typical).
  Total analog budget is well under 1 mA — weeks on a small cell.
- **Analog-only detection.** No MCU in the signal path: amplify, filter,
  compare, one-shot. Simple, deterministic, low power.
- **Fixed topology, tunable values.** The v3-1 PCB layout exists; this
  simulation stack exists precisely to find the best *component values*
  within that topology before touching copper.

The simulator's job: faithfully reproduce the physical dynamics of this
chain (validated against tank behavior), so value choices transfer
straight to the board.

## 2. Current hardware (v3-1), component by component

Signal path: electrodes → AC-coupled bias network → INA333 → output
filter → MCP6561 comparator → monostable/LED.

### Mid-rail reference (U1 OPA333 + R1/R2/R10/C19/C20)

| Part | Value | Purpose |
|------|-------|---------|
| R1, R2 | 1 MΩ each | Divide 3.3 V to 1.65 V mid-rail (only 1.65 µA burned) |
| C19 | 100 nF | Quiets the high-impedance divider node |
| U1 (OPA333) | — | Buffers the divider so VREF can source/sink current |
| R10 | 22 Ω | In the buffer's output/feedback network (per netlist, between VREF and U1−) — helps tolerate the capacitive load on VREF |
| C20 | 100 nF | Local VREF reservoir |

Single-supply operation requires everything to be biased around a
mid-rail "virtual ground." VREF feeds the input bias resistors, the INA
REF pin, C5's cold end, and the threshold divider — **which also makes it
a shared coupling path** (see §4).

### Input coupling and bias (C2/C3, R4/R7, R6/R8, R15, C4)

| Part | Value (stock) | Purpose |
|------|---------------|---------|
| C2, C3 | 4.7 nF | AC-coupling: block electrode DC offset and half-cell drift; with the ~950 kΩ load they form the ~59 Hz differential high-pass |
| R4, R7 | 100 kΩ | Series isolation: limit input current, protect the INA, and (with C4) set the differential low-pass |
| R6, R8 | 10 MΩ | Bias the floating INA inputs to VREF without loading the signal (sets input common mode) |
| R15 | 1 MΩ | Differential termination: defines the differential source impedance seen by the INA (~166 kΩ with 2·R4 ∥ R15) |
| C4 | 330 pF | Differential low-pass with that source impedance; kills RF/EMI **and — as we learned — damps the front end** |

This passive network is the part we spent the campaign testing. Its two
corners bracket the EOD band: high-pass ~59 Hz (drift rejection),
low-pass ~3 kHz at stock C4 (which is actually *inside* the band —
motivating the C4 = 47 pF recommendation that moves it to ~20 kHz).

### Gain stage (U6 INA333 + R3)

R3 = RG sets gain: G = 1 + 100 kΩ/RG. Stock 100 kΩ → G = 2; recommended
51 kΩ → G ≈ 3. The INA333 gives high CMRR at µA supply current, but it's
a 350 kHz-GBW, 0.16 V/µs part — its output stage **cannot drive nF-scale
capacitance** gracefully, which is the root of the instability found in
this campaign.

### Output filter (C5, R9)

| Part | Value (stock) | Purpose |
|------|---------------|---------|
| C5 | 2.2 nF | **Shunt** from ELEC_OUT to VREF — intended as a noise snubber on the comparator path |
| R9 | 4.7 kΩ | Series element into COMP_IN; with R5 sets the hysteresis divider |

C5 sits **directly on the INA output** (upstream of R9, so R9 cannot
isolate the amp from it) — the single most consequential placement on the
board (see §3). Bench + sim verdict: its filtering job is already done by
C4 and the amp's own bandwidth, so it should be deleted or kept ≤ 470 pF.

### Detection (U3 MCP6561, RV1 + R13/R17, R5)

| Part | Value | Purpose |
|------|-------|---------|
| R13/R17 + RV1 | 5.1 kΩ / 330 Ω + trimmer | Threshold divider: VTHRESH ≈ 1.85 V (~200 mV above VREF), field-adjustable |
| U3 (MCP6561) | — | Push-pull rail-to-rail comparator, ~100 µA |
| R5 | 1 MΩ | Positive feedback COMP_IN←TRIGGER: ~15 mV hysteresis band |

The R5/R9 hysteresis is physically correct on the board and in the sim
(the behavioral comparator model keeps it). ~15 mV gives exactly one
edge per pulse in every clean test; smaller R5 backfires by dividing
COMP_IN down and raising the effective threshold.

### Downstream (not simulated)

Monostable (R11/C6 pulse stretch, R14/C9) and LEDs. These only shape
TRIGGER for visibility; they faithfully relay whatever the comparator
does — including 47 kHz chatter.

## 3. What this build taught us

1. **The front end can self-oscillate, and it looks like "stuck on."**
   With stock C5 = 2.2 nF, dropping C4 below ~40 pF (or removing it —
   the bench condition that reproduced the tank failure) lets the INA
   output ring against C5 in a self-sustaining ~48 kHz oscillation.
   TRIGGER chatters rail-to-rail indefinitely. The comparator is
   innocent; the loop is entirely INA output ↔ C5.
2. **C4 is a stability component, not just a bandwidth trim.** Large C4
   band-limits the edges reaching the amplifier and keeps the resonance
   damped. That's why the board "worked" at 330 pF and failed with C4
   absent.
3. **C5 is not worth keeping — bench-confirmed.** With C5 = 2.2 nF
   (R9 = 10 kΩ) the bench showed a sustained ~80 kHz, ~220 mV pk-pk ring
   at ELEC_OUT; removing C5 eliminated it, matching the sim's predicted
   mechanism (sim frequency ~48 kHz — the difference is the macromodel's
   approximate output impedance). Sims with C5 open are identical to
   470 pF for detection (rounded, square, near-threshold). Its filtering
   is redundant: C4 (~20 kHz) and the INA's closed-loop bandwidth
   (~115 kHz at G = 3) already band-limit the path, and chatter immunity
   comes from R5/R9 hysteresis. Delete it, or keep ≤ 470 pF as EMI
   insurance. R9 stays — it is load-bearing for hysteresis.
4. **Detection margin wants G ≈ 3 and C4 = 47 pF.** At VTHRESH = 1.85 V:
   stock (G=2, C4=330p) needs ≥300 mV pulses; the recommended combo
   detects 100 mV pulses with in-band fidelity preserved (~78% of peak
   at 200 µs vs 47% stock).
5. **Electrodes are a first-class circuit element.** Each wire is
   ~15 kΩ of spreading resistance (Randles cell); *mismatch* between the
   two converts common-mode to differential and skews the biphasic
   lobes. Bare Ag drifts (mV over seconds–minutes); Ag/AgCl mostly fixes
   drift but not mismatch. Now partially modeled
   (`--electrode-mismatch`).
6. **The slow-drift path is under control.** The ~59 Hz input high-pass
   attenuates 20–30 Hz water artifacts to roughly a third at the INA
   inputs; no drift-induced false triggers in any combined test.
7. **VREF is a shared node.** In sim it is ideal; on the board, C5's
   current is dumped into the OPA333 buffer and can bounce the bias
   network, INA REF, and threshold divider together — one plausible
   reason the real board fails *more easily* than the sim.

## 4. Future enhancements

Ordered by invasiveness. Everything in tiers 1–2 uses jellybean 0402/0603
parts (C0G/NP0 ceramics, E24 1% resistors) available from any distributor.

### Tier 0 — value swaps only (do these)

| Change | From → To | Why |
|--------|-----------|-----|
| **C5** | 2.2 nF → **removed** (or ≤ 470 pF C0G) | Bench-confirmed oscillator (80 kHz ring at ELEC_OUT; gone with C5 out). Detection is identical without it — its filtering is redundant. The single highest-value change on the board |
| **R3** | 100 kΩ → **51 kΩ** (G ≈ 3) | Detects 100 mV pulses at the stock threshold; keeps headroom |
| **C4** | 330 pF → **47 pF** (C0G) | Moves the in-band low-pass corner from ~3 kHz to ~20 kHz; preserves pulse fidelity. Safe *once C5 is removed/reduced*; never populate below 47 pF with stock C5, and never leave it off |
| C2, C3 | keep 4.7 nF (or 2.2 nF if drift dominates in practice) | 2.2 nF halves LF bleed-through for ~6% peak loss |
| R5, R9, RV1 | keep | Verified correct as-is; R9 is load-bearing for the R5/R9 hysteresis divider (R9 = 10 kΩ also fine — widens the band to ~33 mV) |

Use C0G/NP0 dielectric for C4 (and C5, if populated) — X7R at these small
values varies with bias and temperature, and C4 sits at a stability
boundary.

### Tier 1 — PCB hacks worth doing on existing boards

- **Series isolation resistor between U6 output and C5** (~100–330 Ω).
  The textbook fix for capacitive loading: it damps the resonance for
  *any* C5. Hack: lift C5's ELEC_OUT pad and bridge with an 0402
  resistor stacked on end. Only relevant if a cap is populated in the C5
  position at all (with C5 removed — the current recommendation — there
  is nothing to isolate). With R9 ≥ 10 kΩ downstream, the divider loss
  at COMP_IN is ≤ 3%.
- **Chloride the electrodes (Ag/AgCl).** Removes the dominant drift
  failure mode for the cost of a bleach dip or anodizing in KCl. Note
  the wearable caveat: thin AgCl layers deplete under sustained bias —
  soak-test before a long deployment.
- **Conformal-coat the input network.** R6/R8 are 10 MΩ; on a wearable
  in water, surface moisture leakage across those nodes rivals the
  intended bias currents. Acrylic or silicone coat over the C2–C4/R4–R8
  region (leave the electrode terminals exposed).
- **Add a scope point on ELEC_OUT** (wire to a via or pad) if not
  already accessible — the definitive stuck-on diagnostic is a
  tens-of-kHz oscillation there.

### Tier 2 — next board spin (same topology, minor edits)

- **Footprint for the U6-output series resistor** (0 Ω default). Free
  insurance, zero layout disruption.
- **Stiffen VREF locally**: bump C20 to 1 µF and verify R10 = 22 Ω
  against the OPA333's capacitive-load tolerance; consider separate RC
  decoupling for the threshold divider branch so comparator-side
  transients don't modulate VTHRESH through the shared node.
- **Tolerance-match the input pairs**: specify C2/C3 at ±5% (C0G) and
  R4/R7 at ±0.1% if available (0402 thin-film 0.1% 100 kΩ is a stocked
  part). Mismatch here converts common-mode to differential exactly like
  electrode mismatch does — it's the half of the CM→DM budget we control.
- **Guard ring or increased clearance** around the INA input nodes
  (10 MΩ bias) to reduce leakage sensitivity.
- **Test pads for electrode impedance measurement** (drive a small
  current, read voltage) so field units can verify electrode health.

### Tier 3 — directions we considered and deliberately deferred

- **MCU/DAC threshold, digital detection.** Contradicts the analog
  micropower intent; RV1 is adequate. Not recommended.
- **Higher-order filtering / active filters.** More op-amps, more µA,
  more instability surface. The passive corners are sufficient once C4
  and C5 are right.
- **Full Randles electrode modeling + common-mode source in sim.**
  Remaining work item (see ELECTRODES.md): per-electrode Rs ∥ (Cdl+Rct),
  drift source, and a CM/gradient source to produce a *tolerance budget*
  for mismatch × pickup. Do this pass before betting a long field
  deployment on threshold margins.
- **New amplifier.** The INA333's capacitive-load sensitivity is real
  but fully managed by C5/isolation-R. Any pin-compatible alternative
  with more drive costs supply current; not worth it.

## 5. Open questions

1. Does the bench show the predicted tens-of-kHz oscillation at U6's
   output during a stuck-on event? (Confirms the mechanism on hardware.)
2. Where does the real stability boundary sit with actual electrodes
   attached? (Electrode Rs interacts with the same input corner — re-run
   the C4 sweep with `--electrode-mismatch` once tank-validated.)
3. How fast do chlorided electrodes deplete in the wearable duty cycle?
   (Bench soak test, not SPICE.)
4. What is the actual CM pickup amplitude in the tank? One measurement
   would anchor the deferred CM→DM simulation pass.
