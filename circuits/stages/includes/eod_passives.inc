* Input coupling and bias network (KiCad EOD_Detector_v3-1)
C2 elec_a n_c2a {C_COUPLE}
R4 n_c2a ina_p {R_SERIES}
C3 elec_b n_c3b {C_COUPLE}
R7 n_c3b ina_n {R_SERIES}
R6 vref ina_p {R_VREF}
R8 vref ina_n {R_VREF}
R15 ina_p ina_n {R_DIFF}
C4 ina_n ina_p {C_DIFF}
