# Stage 00 — INA333 sanity check

Baseline test bench: INA333 only, EOD-like differential pulse input, no additional passives.

Use this stage to verify ngspice, waveform generation, and gain after any toolchain or model changes.

## Benches

| File | Model |
|------|-------|
| `bench_ideal.cir` | Ideal 3-op-amp INA333 |
| `bench_ti.cir` | TI macromodel (`circuits/models/ina333_ti.lib`) |

## Run

```bash
python scripts/run_stage.py --stage 00_sanity_ina333
python scripts/run_ina333.py                    # same stage (alias)
python scripts/run_stage.py --stage 00_sanity_ina333 --model ti
```

## Expected

At gain=100 and 1 mV differential pulses, measured gain should be ~100 V/V (ideal) or ~101 V/V (TI).

## Outputs

| Artifact | Description |
|----------|-------------|
| `00_sanity_ina333_waveforms_<bench>.png` | Full train overview |
| `00_sanity_ina333_pulse1_<bench>.png` | Single-pulse zoom: Vin diff (left) vs Vout−REF (right) |

Use `--waveform rounded --sample-us 1` for analog dynamics. Adjust zoom with `--pulse-index` and `--pulse-margin-us`.
