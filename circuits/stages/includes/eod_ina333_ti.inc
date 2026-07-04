* INA333 (U6) — TI macromodel, RG = 100k -> G = 2 V/V
.include "../../models/ina333_ti.lib"

R3 RGp RGn {RGVAL}
XU6 ina_p ina_n 3 0 elec_out vref RGp RGn INA333
Rload_amp elec_out vref 1Meg
