* Differential electrode stimulus from Python filesource
Ain %v[elec_a elec_b] diff_src
.model diff_src filesource (
+ file="input_diff.txt"
+ amploffset=[0 0]
+ amplscale=[1 1]
+ timeoffset=0
+ timescale=1
+ timerelative=false
+ amplstep=false
+ )
