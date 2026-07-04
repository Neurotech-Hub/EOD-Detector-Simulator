# Circuit stages

Simulations are organized as numbered **stages** — incremental slices of the real EOD detector schematic.

## Progression

| Stage | Folder | Status | Description |
|-------|--------|--------|-------------|
| 00 | [`00_sanity_ina333/`](00_sanity_ina333/) | active | INA333 only — regression / sanity check |
| 00 | [`00_sanity_mcp6561/`](00_sanity_mcp6561/) | active | MCP6561 comparator threshold step |
| 01 | [`01_passives/`](01_passives/) | active | Electrode coupling + INA bias network |
| 02 | [`02_frontend/`](02_frontend/) | active | Passives + INA333 (G=2) + output filter |
| 03 | [`03_detector/`](03_detector/) | active | Full front-end + MCP6561 comparator |

Shared netlist fragments: [`includes/`](includes/)

Run any active stage:

```bash
python scripts/run_stage.py --list
python scripts/run_stage.py --stage 01_passives --waveform rounded
python scripts/run_stage.py --stage 02_frontend --waveform rounded
python scripts/run_stage.py --stage 03_detector --waveform rounded
```

Outputs land in `outputs/stages/<stage_id>/`.

## Shared resources

- **`circuits/models/`** — Reusable subcircuits and vendor models (INA333, MCP6561, …). See [`models/README.md`](../models/README.md).
- **`circuits/stages/includes/`** — Shared netlist fragments from KiCad schematic
- **`circuits/stages/_template/`** — Copy to start a new stage

## Adding a stage

1. Create `circuits/stages/NN_name/` with `README.md` and bench netlist(s)
2. Use `.include "../includes/..."` for shared fragments
3. Use `file="input_diff.txt"` in filesource blocks (patched at run time)
4. Add an entry to `src/eod_sim/stages/registry.py`
5. Run and commit

See [`_template/README.md`](_template/README.md) for a checklist.
