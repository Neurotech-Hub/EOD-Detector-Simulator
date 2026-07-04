* INA333 (U6) — ideal model, RG = 100k -> G = 2 V/V
.include "../../models/ina333_ideal.sub"

R3 RGp RGn {RGVAL}
XU6 ina_p ina_n RGp RGn elec_out vref 3 0 INA333_IDEAL RGGAIN={RGVAL}
Rload_amp elec_out vref 1Meg
