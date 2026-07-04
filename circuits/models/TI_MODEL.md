# TI INA333 SPICE Model

The repo includes an ngspice-compatible copy of the TI macromodel at [`ina333_ti.lib`](ina333_ti.lib).

**Source:** Texas Instruments INA333 TINA-TI Spice Model (SBOM310E / INA333.LIB, Rev 1.2, Feb 2019)

## Usage

```bash
python scripts/run_ina333.py --model ti
python scripts/run_ina333.py --model ideal   # default, faster
```

Compare outputs side by side:

```bash
python scripts/run_ina333.py --model ideal
python scripts/run_ina333.py --model ti
# -> outputs/ina333_waveforms_ideal.png
# -> outputs/ina333_waveforms_ti.png
```

## ngspice patches applied

The vendor file required these changes to run in ngspice:

| Issue | Patch |
|-------|-------|
| `TEMP` in VOS drift expressions | Fixed at DC (27 °C nominal) |
| PSpice `IF()` | Ternary `? :` operator |
| PSpice `LIMIT()` | Nested ternary clamp |
| PSpice `VSWITCH` | ngspice `SW` (Vt/Vh from VON/VOFF) |

See the header comment in `ina333_ti.lib` for details.

## Pin order

TI subcircuit: `INA333 IN+ IN- VCC VEE OUT REF RG+ RG-`

Bench instance in [`ina333_bench_ti.cir`](../ina333_bench_ti.cir):

```spice
XU1 in_p in_n VDD 0 out REF RGp RGn INA333
```

## Gain = 1 note

Per TI forum guidance, for unity gain set RG to a very large value (e.g. 1 TΩ) rather than leaving RG pins open.

## Updating the model

To refresh from a new TI download:

1. Copy the vendor `INA333.LIB` to this directory
2. Re-apply the patches listed above (or diff against `ina333_ti.lib`)
3. Verify with `python scripts/run_ina333.py --model ti`
