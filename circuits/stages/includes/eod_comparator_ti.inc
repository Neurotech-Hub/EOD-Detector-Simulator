* MCP6561 comparator (U3) — fixed threshold, potentiometer omitted
.include "../../models/mcp6561.lib"

Vthresh thresh 0 {VTHRESH}
XU3 comp_in thresh 3 0 comp_out MCP6561
Rload_comp comp_out 0 10k

* Stabilize ESD network when COMP_IN is driven by TI INA333 macromodel output
Cstab comp_in 0 100n
