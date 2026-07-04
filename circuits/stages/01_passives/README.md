# Stage 01 — Input passives

Electrode coupling (4.7 nF + 100 kΩ), INA bias resistors (10 MΩ to VREF), and differential network (R15, C4).

No active devices — validates HPF response and DC bias at INA inputs.

## Run

```bash
python scripts/run_stage.py --stage 01_passives --waveform rounded
```

## Expected

- INA+ / INA− DC bias ≈ 1.65 V (VREF)
- Differential pulse appears at INA inputs after coupling caps charge
- Overview: electrode diff (top) vs INA input diff (bottom)
