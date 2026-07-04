# Stage 03 — Full detector

Complete KiCad front-end: passives, INA333 (G=2), output filter, and MCP6561 comparator with fixed threshold.

## Simplifications

- OPA333 reference buffer → ideal `VREF = 1.65 V`
- Potentiometer divider → fixed `VTHRESH = 1.85 V` (tune with `--vthresh`)

## Run

```bash
python scripts/run_stage.py --stage 03_detector --waveform rounded
python scripts/run_stage.py --stage 03_detector --model ti --waveform rounded
python scripts/run_stage.py --stage 03_detector --waveform rounded --vthresh 1.70 --pulse-mv 50
```

## TI bench

The `ti` variant uses the vendor INA333 macromodel. Stage 03 also includes comparator stabilization (`eod_comparator_ti.inc`) and relaxed transient options (`sim_ti_transient.inc`) for ngspice convergence.

## Notes

With G=2, a 1 mV EOD produces ~2 mV at ELEC_OUT. The default threshold (1.85 V) is ~200 mV above the 1.65 V reference — a 1 mV pulse will **not** trigger the comparator. Increase `--pulse-mv` or lower `--vthresh` to explore detection.

## Expected

- Comparator output toggles between ~0 V and ~3.3 V when COMP_IN crosses VTHRESH
