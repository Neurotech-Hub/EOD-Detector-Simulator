* Output coupling to comparator input (C5, R9)
* R5 (hysteresis to TRIGGER) lives in the comparator includes — it only
* exists when the MCP6561 is populated, so stage 02 has no floating node.
C5 vref elec_out {C_OUT}
R9 elec_out comp_in {R_COMP}
