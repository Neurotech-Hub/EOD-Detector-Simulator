* Relaxed transient options for the TI INA333 vendor macromodel
* (the detector's comparator is behavioral — eod_comparator_behavioral.inc —
* so the stiff MCP6561 macromodel is no longer part of transient benches).
.options trtol=100 reltol=1e-2 abstol=1e-5 chgtol=1e-9 method=gear maxord=2
.param TMAX=10u
