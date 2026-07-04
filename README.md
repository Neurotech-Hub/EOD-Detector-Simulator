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

Opens `http://127.0.0.1:8050` with three analysis tabs (Input/ELEC_OUT, Input/COMP_IN, Comparator), overview vs single-pulse zoom, and pulse rate in **kHz** (default 0.5 kHz).

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

Enable `--lf-offset` to superimpose a slow differential sine on the EOD pulse train. Each run draws frequency in **10–30 Hz** (20 ± 10 by default) and a random phase relative to the first pulse. Use this to validate the input high-pass network (4.7 nF + 100 kΩ per side, ~338 Hz cutoff in `01_passives`): in **Overview** view you should see large slow swings at the electrodes with much smaller residual at the INA inputs when the filter is working.

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

```bash
python scripts/run_stage.py --stage 01_passives --waveform rounded --c-couple 10n --r-series 47k
```

The tuning GUI shows an **INA input network** panel for stages `01_passives`, `02_frontend`, and `03_detector`. Pair with `--lf-offset` and **Overview** view to validate HPF attenuation of slow water artifacts.

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
    ├── 03_detector/          Full front-end + MCP6561
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
pytest
```
