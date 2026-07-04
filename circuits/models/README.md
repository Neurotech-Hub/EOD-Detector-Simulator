# Shared SPICE models

Reusable subcircuits and vendor macromodels for all simulation stages.

| Model | File | Wrapper | Docs |
|-------|------|---------|------|
| INA333 ideal | [`ina333_ideal.sub`](ina333_ideal.sub) | `INA333_IDEAL` | — |
| INA333 TI | [`ina333_ti.lib`](ina333_ti.lib) | `INA333` | [`TI_MODEL.md`](TI_MODEL.md) |
| MCP6561 comparator | [`mcp6561.lib`](mcp6561.lib) | `MCP6561` | [`MCP6561.md`](MCP6561.md) |

Include from stage netlists with a path relative to the stage folder:

```spice
.include "../../models/mcp6561.lib"
```
