# Stage 03 — Full detector

Complete KiCad front-end: passives, INA333 (G=2), output filter, and a behavioral MCP6561 comparator equivalent with fixed threshold.

## Simplifications

- OPA333 reference buffer → ideal `VREF = 1.65 V`
- RV1 potentiometer divider (R13/R17) → fixed `VTHRESH = 1.85 V` (tune with `--vthresh`)
- MCP6561 → behavioral comparator (`eod_comparator_behavioral.inc`): threshold comparison, rail-to-rail push-pull output, and hysteresis from the physical R5/R9 network

## Run

```bash
python scripts/run_stage.py --stage 03_detector --waveform rounded
python scripts/run_stage.py --stage 03_detector --model ti --waveform rounded
python scripts/run_stage.py --stage 03_detector --waveform rounded --vthresh 1.70 --pulse-mv 50
```

## Benches

Both variants use the behavioral comparator (`eod_comparator_behavioral.inc`) and converge deterministically:

- `ideal` — ideal INA333 model
- `ti` — TI INA333 vendor macromodel with relaxed transient options (`sim_ti_transient.inc`)

The Microchip MCP6561 macromodel was **retired from these benches**: its ESD clamp diodes collapsed the ngspice timestep non-deterministically when cascaded with the INA333 macromodel (see [MCP6561.md](../../models/MCP6561.md)). Hysteresis behavior is unchanged — it comes from the physical R5/R9 network, which is fully modeled.

## Notes

With G=2, a 1 mV EOD produces ~2 mV at ELEC_OUT. The default threshold (1.85 V) is ~200 mV above the 1.65 V reference — a 1 mV pulse will **not** trigger the comparator. Increase `--pulse-mv` or lower `--vthresh` to explore detection.

## Expected

- Comparator output toggles between ~0 V and ~3.3 V when COMP_IN crosses VTHRESH
