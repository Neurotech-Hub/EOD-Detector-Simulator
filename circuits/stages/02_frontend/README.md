# Stage 02 — INA333 front-end

Full input network plus INA333 (U6, RG = 100 kΩ → G = 2 V/V) and output coupling (C5, R9, R5) to comparator input.

## Run

```bash
python scripts/run_stage.py --stage 02_frontend --waveform rounded
python scripts/run_stage.py --stage 02_frontend --model ti --waveform rounded
```

## Expected

- Measured gain at ELEC_OUT ≈ 2 V/V
- Pulse zoom: INA input diff vs ELEC_OUT − VREF
