# Stage template

Copy this folder to `circuits/stages/NN_short_name/` when adding a new simulation stage.

## Checklist

- [ ] Rename folder with numeric prefix (e.g. `03_detection`)
- [ ] Write `README.md` — purpose, schematic reference, how to run
- [ ] Add `bench.cir` (or `bench_ideal.cir` / `bench_ti.cir` if model variants)
- [ ] Include shared models via `.include "../../models/your_part.sub"`
- [ ] Use `file="input_diff.txt"` for Python-generated waveforms
- [ ] Add `.save` for nodes you want to plot
- [ ] Register in `src/eod_sim/stages/registry.py`:
  - `status="active"` when runnable
  - `benches` mapping model key → netlist filename
  - `supports_eod_input=True` if using the standard pulse train
- [ ] Run: `python scripts/run_stage.py --stage NN_short_name`
- [ ] Update the table in `circuits/stages/README.md`

## bench.cir.template

See `bench.cir.template` in this folder for a minimal starting netlist.
