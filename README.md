# EOD Detector — ngspice INA333 Simulation

Simulate an INA333 instrumentation amplifier front-end driven by EOD-like differential pulse trains. Python generates waveforms, runs ngspice in batch CLI mode, parses results, and plots input/output waveforms.

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

```bash
python scripts/run_ina333.py
python scripts/run_ina333.py --model ti
```

This will:

1. Generate a biphasic differential pulse train waveform file in `outputs/`
2. Run ngspice on the selected bench netlist (`ideal` or `ti`)
3. Save `outputs/ina333_waveforms_<model>.png`

### Options

```bash
python scripts/run_ina333.py --model ti --gain 100 --pulse-mv 1.0 --isi-ms 20 --plot plotly
```

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | ideal | `ideal` (3-op-amp) or `ti` (TI macromodel) |
| `--gain` | 100 | INA333 gain (sets RG = 100k / (G - 1)) |
| `--pulse-mv` | 1.0 | Peak differential pulse amplitude (mV) |
| `--isi-ms` | 20 | Inter-pulse interval (ms) |
| `--num-pulses` | 4 | Number of pulses in the train |
| `--plot` | matplotlib | `matplotlib` or `plotly` |
| `--duration-ms` | 100 | Simulation duration (ms) |

## Project layout

```
circuits/           SPICE netlists and subcircuit models
src/eod_sim/        Python package (waveforms, ngspice runner, plotting)
scripts/            CLI entry points
outputs/            Generated PWL, raw, plots (gitignored)
tests/              Unit tests
```

## TI vendor model

The default simulation uses an ideal 3-op-amp INA333 subcircuit. The TI macromodel is vendored and patched at [`circuits/models/ina333_ti.lib`](circuits/models/ina333_ti.lib). Run with `--model ti`. See [circuits/models/TI_MODEL.md](circuits/models/TI_MODEL.md) for patch details.

## Manual ngspice run

Generate the waveform file first with the Python script, then:

```bash
ngspice -b -r outputs/simulation.raw outputs/ina333_bench_run.cir
```

The run netlist is written to `outputs/` with paths patched for that directory.

## Tests

```bash
pytest
```
