# Stage 02 — INA333 front-end

Full input network plus INA333 (U6, RG = 100 kΩ → G = 2 V/V) and output coupling (C5, R9) to the comparator input node. The hysteresis resistor R5 and the MCP6561 are not populated in this stage — COMP_IN is observed open-circuit (high-impedance), as a scope probe would see it. TRIGGER does not exist here.

## Run

```bash
python scripts/run_stage.py --stage 02_frontend --waveform rounded
python scripts/run_stage.py --stage 02_frontend --model ti --waveform rounded
```

## Expected

- Measured gain at ELEC_OUT ≈ 2 V/V
- Pulse zoom: INA input diff vs ELEC_OUT − VREF
