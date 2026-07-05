* MCP6561 comparator (U3) — behavioral equivalent (deterministic)
*
* Replaces the Microchip macromodel for transient runs: the vendor model's
* ESD clamp diodes (D98/D99, IS=1e-15) collapse the ngspice timestep
* non-deterministically when cascaded with the INA333 macromodel.
* This core reproduces the electrically relevant behavior:
*   - threshold comparison against VTHRESH (board: RV1 wiper via R13/R17)
*   - rail-to-rail push-pull output referenced to the actual supply v(3)
*   - ~50 ns propagation-delay pole (negligible vs 200-1000 us EODs)
*   - hysteresis from the PHYSICAL R5 feedback network, exactly as on
*     the PCB: TRIGGER swing through R5 against the R9 source impedance
*     shifts COMP_IN by ~VDD*R9/(R9+R5) (~15 mV at 4.7k/1Meg).

Vthresh thresh 0 {VTHRESH}

* Smooth high-gain transfer (tanh, ~50 uV transition region).
* Steepness is fixed; detection behavior is governed by the physical
* R5/R9 hysteresis network, not by this numerical constant.
.param CMP_STEEP=60k
Bcore ncmp 0 V = 0.5*v(3)*(1 + tanh({CMP_STEEP}*(v(comp_in) - v(thresh))))

* Push-pull output resistance (real tpd ~50 ns is far below the .tran
* step, so no delay pole: a capacitor here only causes numerical ringing)
Rprop ncmp trigger 100

* Conventional bench load on the comparator output
Rload_comp trigger 0 10k

* R5 hysteresis / positive feedback (KiCad: COMP_IN to TRIGGER)
R5 comp_in trigger {R_HYST}
