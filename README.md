# EOD Detector — ngspice Simulation

Simulate the EOD detector front-end in incremental **stages**, from sanity checks through passives and active blocks. Python generates waveforms, runs ngspice in batch CLI mode, parses results, and plots waveforms.

Shared models live in [`circuits/models/`](circuits/models/) (INA333, MCP6561 comparator, …).

## Prerequisites

### ngspice

```bash
brew install ngspice
ngspice -v
```

Or set `NGSPICE` to the full path of the binary if it is not on `PATH`.

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quick start

List stages:

```bash
python scripts/run_stage.py --list
```

Run the INA333 sanity check (regression baseline):

```bash
python scripts/run_stage.py --stage 00_sanity_ina333
python scripts/run_ina333.py                    # same stage (alias)
python scripts/run_stage.py --stage 00_sanity_ina333 --model ti
```

Run the MCP6561 comparator sanity check:

```bash
python scripts/run_stage.py --stage 00_sanity_mcp6561
```

Run the full KiCad schematic incrementally:

```bash
python scripts/run_stage.py --stage 01_passives --waveform rounded
python scripts/run_stage.py --stage 02_frontend --waveform rounded
python scripts/run_stage.py --stage 03_detector --waveform rounded
```

Outputs: `outputs/stages/<stage_id>/`

### Tuning GUI

Interactive local UI for stage selection, parameter tuning, and dual-axis plots:

```bash
pip install -e ".[dev]"   # includes dash
python scripts/run_gui.py
```

Opens `http://127.0.0.1:8050` with three analysis tabs (Electrodes/ELEC_OUT, ELEC_OUT/COMP_IN, Comparator), overview vs single-pulse zoom, and pulse rate in **kHz** (default 0.5 kHz). The Electrodes tab overlays the commanded stimulus (dashed) against the simulated electrode differential so numerical problems are immediately visible.

### Options

```bash
python scripts/run_stage.py --stage 00_sanity_ina333 --gain 100 --pulse-mv 1.0 --plot plotly
python scripts/run_stage.py --stage 00_sanity_ina333 --waveform rounded --pulse-width-us 200
```

Single-pulse zoom (dual y-axis) is generated automatically for EOD input stages. The GUI always zooms the **first pulse** in the train.

```
outputs/stages/00_sanity_ina333/00_sanity_ina333_pulse1_ideal.png
```

| Flag | Default | Description |
|------|---------|-------------|
| `--stage` | `00_sanity_ina333` | Simulation stage id |
| `--model` | (stage default) | Bench variant: `ideal`, `ti`, or `default` |
| `--gain` | 100 | INA333 gain (sets RG = 100k / (G - 1)) |
| `--pulse-mv` | 1.0 | Peak differential pulse amplitude (mV) |
| `--waveform` | square | Pulse shape: `square` (ideal) or `rounded` (smooth lobes) |
| `--pulse-width-us` | 200 | Total biphasic width for rounded waveform (µs) |
| `--sample-us` | auto | Waveform + `.tran` step (µs): 1 rounded, 10 square |
| `--no-pulse-zoom` | off | Skip single-pulse dual-axis plot (CLI only) |
| `--isi-ms` | 20 | Inter-pulse interval (ms) |
| `--num-pulses` | 4 | Number of pulses in the train |
| `--plot` | matplotlib | `matplotlib` or `plotly` |
| `--duration-ms` | 100 | Simulation duration (ms) |
| `--vref` | stage default | Reference voltage (V); 1.65 for KiCad stages |
| `--vthresh` | 1.85 | Comparator threshold (V) for stage 03 |
| `--vdd` | stage default | Supply voltage (V); 3.3 for KiCad stages |
| `--lf-offset` | off | Add slow sinusoidal differential offset (water artifact) |
| `--lf-offset-mv` | 100 | Peak LF offset amplitude (mV) |
| `--lf-offset-center-hz` | 20 | LF offset center frequency (Hz) |
| `--lf-offset-span-hz` | 10 | Draw f uniformly in [center−span, center+span] |
| `--lf-offset-seed` | (random) | Optional RNG seed for reproducible f and phase |

### Slow LF offset (water recording)

Enable `--lf-offset` to superimpose a slow differential sine on the EOD pulse train. Each run draws frequency in **10–30 Hz** (20 ± 10 by default) and a random phase relative to the first pulse. Use this to validate the input high-pass network in `01_passives`: the differential corner is ~59 Hz (2.35 nF effective coupling into the ~950 kΩ R15/R6 load), so a 20 Hz offset is attenuated to roughly a third at the INA inputs. In **Overview** view you should see large slow swings at the electrodes with a visibly smaller residual at the INA inputs when the filter is working.

```bash
python scripts/run_stage.py --stage 01_passives --waveform rounded --lf-offset --lf-offset-mv 150 --duration-ms 50
```

The tuning GUI exposes the same controls under **Slow water offset (~20 Hz)** in the Waveform section.

### INA input network (stages 01–03)

Tune the symmetric INA333 input passive network. Values are SPICE literals applied to both legs (or the shared differential element). INA gain stays fixed at G=2 (RG = 100k).

| Flag | Default | Component |
|------|---------|-----------|
| `--c-couple` | `4.7n` | Input coupling cap (C2, C3) |
| `--r-series` | `100k` | Series input resistor (R4, R7) |
| `--r-vref` | `10Meg` | VREF bias resistor (R6, R8) |
| `--r-diff` | `1Meg` | Differential input resistor (R15) |
| `--c-diff` | `330p` | Differential input capacitor (C4) |
| `--electrode-mismatch` | `0` | Electrode impedance mismatch (%) — see below |

```bash
python scripts/run_stage.py --stage 01_passives --waveform rounded --c-couple 10n --r-series 47k
```

The tuning GUI shows an **INA input network** panel for stages `01_passives`, `02_frontend`, and `03_detector`. Pair with `--lf-offset` and **Overview** view to validate HPF attenuation of slow water artifacts.

### Electrode impedance mismatch (stages 01–03)

`--electrode-mismatch <pct>` (GUI: **Electrode mismatch (%)** in the INA
input network panel) inserts a per-electrode source resistance between the
stimulus and `ELEC_A`/`ELEC_B`:

- **0 (default):** ideal stiff drive (1 mΩ) — identical to the previous
  behavior.
- **m > 0:** enables the electrode model with nominal Rs = **15 kΩ** (fine
  Ag wire, ~5 mm exposed, fresh water — see
  [ELECTRODES.md](ELECTRODES.md)), split ±m/2 between the two electrodes:
  `R_ELEC_A = 15k·(1 + m/200)`, `R_ELEC_B = 15k·(1 − m/200)`.

This demonstrates the two in-band electrode effects from ELECTRODES.md
within the current differential-stimulus architecture: **amplitude droop**
(Rs against C4 forms a ~16 kHz corner at stock values) and **one-sided
biphasic distortion** (unequal Rs against the C2/R4 vs C3/R7 legs skews the
two lobes). With mismatch on, the dashed "Commanded stimulus (ideal)"
overlay in the Electrodes tab visibly departs from the simulated electrode
differential — physically this time, not numerically.

```bash
python scripts/run_stage.py --stage 01_passives --waveform rounded --pulse-mv 300 --electrode-mismatch 20
```

### Comparator network (stages 02–03)

Tune output coupling and hysteresis between INA output and comparator input.

| Flag | Default | Component |
|------|---------|-----------|
| `--c-out` | `2.2n` | Output coupling cap (C5, VREF–ELEC_OUT) |
| `--r-comp` | `4.7k` | Series resistor ELEC_OUT–COMP_IN (R9) |
| `--r-hyst` | `1Meg` | Hysteresis resistor COMP_IN–TRIGGER (R5, stage 03 only) |

The tuning GUI shows a **Comparator network** panel for `02_frontend` and `03_detector`. R5 only applies to `03_detector` — stage 02 has no comparator, so it does not exist there.

Stage 03's comparator is a **behavioral MCP6561 equivalent** ([`eod_comparator_behavioral.inc`](circuits/stages/includes/eod_comparator_behavioral.inc)): threshold comparison against `VTHRESH`, rail-to-rail push-pull output, and hysteresis produced by the **physical R5/R9 network** exactly as on the board (TRIGGER swing through R5 shifts COMP_IN by ~`VDD·R9/(R9+R5)` ≈ 15 mV at the 4.7k/1Meg defaults). The Microchip vendor macromodel was retired from transient benches — see *Known limitations* below.

## Simulation validation

Every run is validated after ngspice completes; a run only counts as
successful when all checks pass. Otherwise the CLI/GUI reports an explicit
error instead of plotting misleading data.

- ngspice output is scanned for `timestep too small` / aborted-transient
  messages even when the exit code is 0.
- ngspice is killed after a **5-minute timeout** — a convergence-stuck run
  raises a clear error instead of hanging indefinitely.
- The raw file must span the full requested duration, be strictly
  monotonic in time, dense enough to trust, and free of NaN/Inf.
- **Stimulus fidelity:** the differential at the filesource nodes
  (`SRC_A − SRC_B`, upstream of the electrode model) is compared against
  the commanded waveform; any deviation above 1 mV fails the run. The
  filesource is stiff, so deviations indicate solver failure — while
  `ELEC_A/ELEC_B` may legitimately deviate when electrode mismatch is
  enabled.
- The GUI overlays the **commanded stimulus (ideal)** as a dashed trace on
  the Electrodes tab, keeps the previous good result when a run fails, and
  shows amber warnings from the quality checks.

## Board mapping (EOD_Detector_v3-1, value changes only)

Every tunable in this tool maps 1:1 onto a component on the fixed v3-1
topology, so explored values transfer straight back to the PCB:

| Sim parameter / flag | Board designator | Stock value |
|----------------------|------------------|-------------|
| `--c-couple` | C2, C3 | 4.7 nF |
| `--r-series` | R4, R7 | 100 kΩ |
| `--r-vref` | R6, R8 | 10 MΩ |
| `--r-diff` | R15 | 1 MΩ |
| `--c-diff` | C4 | 330 pF |
| `--gain` (sets RG) | R3 | 100 kΩ (G = 2) |
| `--c-out` | C5 | 2.2 nF |
| `--r-comp` | R9 | 4.7 kΩ |
| `--r-hyst` | R5 | 1 MΩ |
| `--vthresh` | RV1 wiper (R13 = 5.1 kΩ, R17 = 330 Ω divider) | 1.85 V default |
| `--electrode-mismatch` | (environment: the electrodes/water, not a PCB part) | 0 % (model off) |

The monostable network (R11/C6 pulse width, R14/C9, LEDs) is downstream of
TRIGGER and not simulated.

## Suggested component values (sim-derived)

From deterministic sweeps with 200 µs rounded biphasic pulses at 0.5 kHz
(standard E-series values; all within the fixed v3-1 topology):

| Designator | Stock | Suggestion | Why (measured in sim) |
|------------|-------|------------|------------------------|
| **C4** | 330 pF | **47 pF — do not go lower** | Biggest win. Against the ~166 kΩ differential source impedance (2·R4 ∥ R15), 330 pF puts the low-pass corner at ~3 kHz — inside the EOD band. A 200 µs pulse keeps only 47% of its peak (32% at 100 µs). 47 pF moves the corner to ~20 kHz: 78% / 73% preserved. **Below ~43 pF the front end self-oscillates at ~48 kHz with stock C5** — see [C4_STABILITY.md](C4_STABILITY.md). |
| **R3** | 100 kΩ (G=2) | **51 kΩ (G≈3)** | At VTHRESH = 1.85 V, G=2 needs ≥300 mV pulses to trigger; G=3 detects 200 mV, and 100 mV once C4 = 47 pF. G=5 (RG = 24 kΩ) detects 100 mV even with stock C4 but eats headroom on large pulses. |
| **C2, C3** | 4.7 nF | keep, or **2.2 nF** if slow drift dominates | 2.2 nF halves the 20–30 Hz bleed-through at the INA inputs (16% vs 32% residual) for only ~6% pulse-peak loss. Keep 4.7 nF if drift is not a problem in practice. |
| **R9** | 4.7 kΩ | keep | COMP_IN tracks ELEC_OUT faithfully across the R9 sweep (200 Ω – 4.7 kΩ all converge and trigger cleanly). No measured benefit to changing. |
| **C5** | 2.2 nF | **470 pF** | 2.2 nF directly loads the INA333 output and forms an under-damped ~48 kHz resonance; with C4 < ~43 pF (or fast input edges) the front end self-oscillates and TRIGGER chatters continuously — the "stuck on" signature. ≤ 1 nF removes the mechanism; 470 pF verified clean for all C4 down to 4.7 pF with identical gain and detection. Details: [C4_STABILITY.md](C4_STABILITY.md). |
| **R5** | 1 MΩ | keep | Gives a ~15 mV hysteresis band: exactly one TRIGGER edge per pulse, no chatter, in every test. Going much smaller backfires — at 100 kΩ the R5 loading divides COMP_IN enough to raise the effective threshold and detection stops entirely. |
| **RV1** (VTHRESH) | ~1.85 V | keep as trim | Margin table: at G=3 with C4 = 47 pF, 100 mV pulses clear 1.85 V. Trim down for weaker signals, up to reject noise. |

Caveats, stated plainly:

- These sweeps optimize **pulse fidelity, slow-drift rejection, and
  threshold margin** against the commanded differential stimulus. Resistive
  **electrode impedance mismatch** can now be enabled
  (`--electrode-mismatch`), but **polarization (double-layer C), half-cell
  drift, and common-mode pickup are still not modeled** (see Deferred
  below), so treat those aspects as unverified by simulation.
- Combined check: with 100 mV LF drift superimposed on 300 mV pulse trains,
  both stock and suggested values produce exactly one trigger per pulse
  with zero drift-induced extras.

## Known limitations and sim-only elements

| Element | Physical? | Notes |
|---------|-----------|-------|
| Behavioral comparator (stage 03) | Equivalent | Reproduces the MCP6561's threshold, rail-to-rail output, and R5/R9 hysteresis; omits input bias/offset details and exact ~50 ns propagation delay (negligible vs 200–1000 µs EODs). |
| MCP6561 vendor macromodel | Retired for transient | Its ESD clamp diodes collapse the ngspice timestep **non-deterministically** when cascaded with the INA333 macromodel; solver sweeps (`sparse`, `rshunt`, `trap`, `itl4`, `cshunt`) either failed or distorted TRIGGER. Still used in the standalone `00_sanity_mcp6561` stage. |
| `Rload_amp` 1 MΩ (ELEC_OUT–VREF) | Bench load | Stabilizes the INA output in simulation. |
| `Rload_comp` 10 kΩ (TRIGGER–GND) | Bench load | Conventional comparator output load. |
| Ideal `VREF` source | Simplified | OPA333 reference buffer omitted ([stage 03 README](circuits/stages/03_detector/README.md)). |
| Ideal `VTHRESH` source | Simplified | RV1 potentiometer divider replaced by a fixed source (`--vthresh`); keep suggested thresholds within RV1's achievable range. |
| `sim_ti_transient.inc` options | Solver tuning | `method=gear`, relaxed tolerances, `TMAX=10u` for the TI INA333 macromodel. |
| XSPICE `filesource` stimulus | Sim input | Stiff voltage source pair on SRC_A/SRC_B; cannot be loaded by the circuit. `R_ELEC_A/B` (electrode mismatch model) sit between the source and ELEC_A/ELEC_B. |

### Deferred: electrode polarization and common-mode (CM-to-DM) modeling

**Resistive electrode mismatch is now modeled** via
`--electrode-mismatch` / the GUI's Electrode mismatch (%) control (per-
electrode series Rs = 15 kΩ ± m/2 between the source and
`ELEC_A/ELEC_B`). Still deferred: **electrode polarization (double-layer
capacitance), half-cell potential drift, and a separate common-mode /
gradient source for CM-to-DM conversion** — the remaining suspects for the
real-world continuous triggering issue. Design notes for bare Ag vs
Ag/AgCl and what to model next: [ELECTRODES.md](ELECTRODES.md).

### Detector convergence

With the behavioral comparator, the full R9 × pulse-shape matrix (200 Ω to
4.7 kΩ, rounded and square) converges deterministically in seconds — verified
by `pytest -m integration`. Any failure is loud: output scanning, post-run
validation, and a 5-minute ngspice timeout guarantee no silent partial plots.

## Project layout

```
circuits/
├── models/              Shared subcircuits (INA333, MCP6561, …)
└── stages/              Incremental simulation stages
    ├── README.md        Stage progression and how to add stages
    ├── 00_sanity_ina333/   INA333-only regression bench
    ├── 00_sanity_mcp6561/  MCP6561 comparator threshold step
    ├── 01_passives/        Electrode coupling + INA bias network
    ├── 02_frontend/          INA333 (G=2) + output filter
    ├── 03_detector/          Full front-end + behavioral comparator
    ├── includes/             Shared netlist fragments
    └── _template/          Copy to start a new stage

src/eod_sim/
├── stages/registry.py   Stage definitions (register new stages here)
├── runner.py            Shared generate -> simulate -> plot pipeline
├── waveforms.py         EOD pulse train generation
├── ngspice.py           Batch CLI runner and netlist patching
├── results.py           Raw file parsing
└── plot.py              Matplotlib / Plotly plots

scripts/
├── run_stage.py         Main CLI for any stage
└── run_ina333.py        Alias for sanity stage

outputs/stages/<stage_id>/   Generated artifacts (gitignored)
tests/                       Unit tests
```

## Adding a stage

1. Create `circuits/stages/NN_name/` with bench netlist(s) — see [`circuits/stages/_template/`](circuits/stages/_template/)
2. Register in [`src/eod_sim/stages/registry.py`](src/eod_sim/stages/registry.py) with `status="active"`
3. Run: `python scripts/run_stage.py --stage NN_name`

Full checklist: [`circuits/stages/README.md`](circuits/stages/README.md)

## TI vendor model

The TI macromodel is at [`circuits/models/ina333_ti.lib`](circuits/models/ina333_ti.lib). Use `--model ti` on the sanity stage. See [`circuits/models/TI_MODEL.md`](circuits/models/TI_MODEL.md).

## Tests

```bash
pytest                    # fast unit tests
pytest -m integration     # end-to-end ngspice runs (slow; requires ngspice)
```
