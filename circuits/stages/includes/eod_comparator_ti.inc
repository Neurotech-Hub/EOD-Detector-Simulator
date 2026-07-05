* MCP6561 comparator (U3) — vendor macromodel, fixed threshold
* DEPRECATED for transient benches: the macromodel's ESD clamp diodes
* collapse the timestep non-deterministically when cascaded with the
* TI INA333. Use eod_comparator_behavioral.inc instead (current default).
.include "../../models/mcp6561.lib"

Vthresh thresh 0 {VTHRESH}
XU3 comp_in thresh 3 0 trigger MCP6561
Rload_comp trigger 0 10k

* R5 hysteresis / positive feedback (KiCad: COMP_IN to TRIGGER)
R5 comp_in trigger {R_HYST}

* Optional stabilization for the MCP6561 ESD network when COMP_IN is driven by
* the TI INA333 macromodel output (sim only; NOT on PCB). Default C_STAB=0
* keeps the netlist physical; set 100n only if convergence fails.
Cstab comp_in 0 {C_STAB}
