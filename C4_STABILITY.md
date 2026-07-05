# C4 stability sweep — front-end oscillation below ~43 pF

**TL;DR:** With the stock output network (C5 = 2.2 nF), the TI INA333 front
end becomes a self-sustaining **~48 kHz oscillator** when C4 drops below
~40 pF. The boundary is sharp (43 pF clean / 39 pF oscillates), it does
**not** require the comparator, and once started it never stops — TRIGGER
chatters rail-to-rail at ~47 kHz indefinitely, which at the monostable/LED
looks exactly like **"comparator stuck on."** Reducing **C5 to ≤ 1 nF
(470 pF recommended)** removes the oscillation entirely and makes C4 a free
choice. Keep **C4 = 47 pF** per the README recommendation, but treat it as
sitting at the edge of the stability region, not just a bandwidth choice.

Context: observed as "strong ringing" in the simulator for C4 < 47 pF, and
suspected as a contributor to the continuous-trigger behavior seen in the
tank. All sweeps: 300 mV rounded biphasic pulses (200 µs), 0.5 kHz, 4
pulses over 20 ms, stock values unless noted, TI bench.

## Symptom and evidence

From the run that prompted this (stage 03 TI, C4 = 22 pF, otherwise stock):

- First TRIGGER edge at 5.016 ms (first pulse), then **677 rising edges**
  at a steady ~47/ms until the end of the simulation — long after the last
  pulse (~11 ms). Self-sustaining, not per-pulse ringing.
- In a stimulus-free window (15–16 ms): `INA_P`/`INA_N` flat to **0.03 mV**,
  while `ELEC_OUT`/`COMP_IN` swing **~0.77 V pk-pk at 47.5 kHz** and
  TRIGGER swings rail-to-rail.
- The waveform is smooth over 10–20 solver points per cycle; where the
  circuit is not oscillating the baseline is quiet to nanovolts.

**Not a solver artifact.** The oscillating stage-02 case (C4 = 33 pF) was
re-run with strict settings (`trtol=1 reltol=1e-4 abstol=1e-10 method=trap`,
61k timepoints) in place of the relaxed TI options: identical behavior
(0.88 V pk-pk at 48 kHz).

## Sweep results

### C4 boundary (stage 03 TI, C5 = 2.2 nF, R5 = 1 MΩ, rounded pulses)

| C4 | Gain 2 | Gain 3 |
|----|--------|--------|
| 330 pF (stock) | clean (4 edges) | clean |
| 100 pF | clean | clean |
| 68 pF | clean | clean |
| **47 pF** | **clean** | **clean** |
| **43 pF** | **clean** | — |
| **39 pF** | **oscillates** (~48 kHz) | — |
| 33 pF | oscillates | oscillates |
| 22 pF | oscillates | oscillates |
| 10 pF | oscillates | oscillates |

The boundary (between 43 and 39 pF) is essentially independent of gain.

### Controls — what the oscillator is and isn't

| Experiment | Result | Conclusion |
|------------|--------|------------|
| Stage 03 **ideal** bench, C4 = 22 pF / 10 pF | clean | The ideal INA (pure gain block) never oscillates → the TI INA333 macromodel's dynamics are the resonant element. |
| Stage 02 (**no comparator**), C4 = 39/33/22 pF | sustained ~754 mV pk-pk at ELEC_OUT | The comparator is **not required** — the INA + C5 output load self-oscillates. The comparator only reports it. |
| Stage 02, C4 = 330 pF | 3.3 mV ring decaying to 0.05 mV after each pulse | The under-damped resonance exists at stock values too; large C4 keeps it damped. |
| Stage 03 TI, C4 = 22 pF, R5 = 470k/330k/220k | all oscillate | More hysteresis does **not** fix it (consistent with the comparator not being in the loop). |
| **Square** pulses, gain 2 | 100 pF clean; **68 pF and 47 pF oscillate** | Faster edges shift the boundary up — the margin at 47 pF depends on the input being band-limited (real EODs are). |

### Mitigation — C5 (stage 03 TI, C4 = 22 pF, rounded)

| C5 | Result |
|----|--------|
| 2.2 nF (stock) | oscillates (~48 kHz) |
| **1 nF** | **clean** |
| **470 pF** | **clean** |
| 220 pF | clean |
| 100 pF | clean |

With C5 = 470 pF the front end is clean for **every C4 tested down to
4.7 pF** (gain 3), and the recommended combo passes even the square-pulse
stress test:

| Configuration (gain 3) | Result |
|------------------------|--------|
| Stock: C4 = 330 pF, C5 = 2.2 nF | clean, measured gain 3.00 |
| README rec: C4 = 47 pF, C5 = 2.2 nF | clean, gain 3.01 |
| **Combo: C4 = 47 pF, C5 = 470 pF** | **clean, gain 3.00 — clean on square pulses too** |

## Mechanism (what the data supports)

- The INA333 is a 350 kHz-GBW, ~0.16 V/µs micro-power amplifier whose
  closed-loop output impedance rises with frequency. **C5 = 2.2 nF sits
  directly on its output** (to VREF), forming an under-damped resonance in
  the tens-of-kHz range — visible as a small decaying ring even at stock
  values. Real amplifiers of this class genuinely misbehave with nF-scale
  direct capacitive loads.
- C4 (against the ~166 kΩ differential source impedance, 2·R4 ∥ R15)
  band-limits what reaches the amplifier. Below ~40 pF the amplified pulse
  edge is fast enough to drive the output stage into a large-signal,
  slew-limited oscillation against C5 that never damps out.
- The oscillation loop is confined to the amplifier + its output load: the
  INA inputs stay flat while it runs, the ideal-INA bench is immune, and
  removing the comparator changes nothing.

## Tank relevance ("comparator stuck on")

Bench tests with **C4 absent** (populated footprint, no cap) reproduced the
same ringing / stuck-on behavior. In the GUI, **Component defaults →
Detector v3 - No C4** models this with C4 = 1 fF (effectively open between
INA+ and INA−); all other values match the KiCad v3 stock network.

A TRIGGER pin oscillating at ~47 kHz continuously retriggers the
monostable and looks exactly like a stuck-on detector. Two reasons the real
board may be **more** susceptible than the sim:

1. **VREF is ideal in simulation.** On the PCB, C5's resonant current is
   dumped into the OPA333 VREF buffer; VREF bounce couples into the input
   bias network (R6/R8), the INA REF pin, and the RV1 threshold divider —
   feedback paths the sim does not represent.
2. **Electrode source impedance** (now modeled via `--electrode-mismatch`)
   raises the differential source impedance and shifts the input corner,
   moving the effective boundary around in the field.

## Recommendations

1. **Never go below C4 = 47 pF** with the stock output network. The
   simulated boundary is 43→39 pF for rounded 200 µs pulses, and moves up
   to ~68–100 pF for fast-edged (square) inputs — 47 pF has thin margin.
2. **Change C5 from 2.2 nF to 470 pF** (standard value; ≤ 1 nF suffices in
   sim). This removes the oscillation mechanism outright, decouples the C4
   choice from stability, and preserves detection and measured gain
   exactly (verified at gain 3, including square-pulse stress).
3. Recommended combo, superseding the "keep C5" line in the README's
   suggested-values table: **gain ≈ 3 (R3 = 51 kΩ), C4 = 47 pF,
   C5 = 470 pF**, R5/R9 stock. R5 is not a lever here — extra hysteresis
   does not stop the oscillation.
4. **Bench verification:** scope U6's output (ELEC_OUT) during a stuck-on
   event and look for a continuous tens-of-kHz oscillation. If present,
   the C5 reduction is the value-change-only fix; a series isolation
   resistor between U6's output and C5 would be the topology-level fix on
   a future board revision.

## Caveats

- The exact boundary values come from the **TI INA333 macromodel**; its
  output-impedance model sets the resonant frequency and damping, so trust
  the mechanism and the ordering, not the picofarad. The qualitative
  warning (nF-scale direct output load + wide input bandwidth =
  under-damped front end) is consistent with known amplifier behavior.
- The behavioral comparator faithfully relays the oscillation but plays no
  role in creating it (verified in stage 02).
- Sweeps used the stiff electrode drive. Electrode impedance
  (`--electrode-mismatch`) adds source resistance that interacts with the
  same corner — re-check margin when exploring electrode effects.

See also: [README](README.md) (suggested component values),
[ELECTRODES.md](ELECTRODES.md).
