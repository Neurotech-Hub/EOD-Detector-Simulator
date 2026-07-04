# Stage 00 — MCP6561 sanity check

Comparator threshold crossing with a PWL step on IN+ against a fixed 2.5 V reference on IN-.

## Expected behavior

| Time | IN+ | IN- | OUT (5 V supply) |
|------|-----|-----|------------------|
| < 1 ms | 1.0 V | 2.5 V | Low (~0 V) |
| > 1 ms | 3.0 V | 2.5 V | High (~5 V) |

## Run

```bash
python scripts/run_stage.py --stage 00_sanity_mcp6561
```

## Model

Uses [`circuits/models/mcp6561.lib`](../../models/mcp6561.lib). Connect VDD to top-level node `3` (ngspice vendor-model quirk — see [`MCP6561.md`](../../models/MCP6561.md)).
