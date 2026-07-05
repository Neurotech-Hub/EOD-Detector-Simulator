* Differential electrode stimulus from Python filesource.
* The filesource drives SRC_A/SRC_B stiffly; R_ELEC_A/R_ELEC_B model the
* per-electrode source (spreading) resistance between the water and the
* electrodes. Defaults of 1 mOhm are electrically identical to a stiff
* drive; the electrode-mismatch model sets them to 15k*(1 +/- m/200).
* See ELECTRODES.md.
Ain %v[src_a src_b] diff_src
.model diff_src filesource (
+ file="input_diff.txt"
+ amploffset=[0 0]
+ amplscale=[1 1]
+ timeoffset=0
+ timescale=1
+ timerelative=false
+ amplstep=false
+ )
R_ELA src_a elec_a {R_ELEC_A}
R_ELB src_b elec_b {R_ELEC_B}
