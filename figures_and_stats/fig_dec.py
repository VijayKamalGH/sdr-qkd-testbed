"""fig_dec.png panel (a): QBER of the three decoders against measured post-MMSE SINR (19 normal-channel captures)
with the matched-R model of Theorem 1 (crosses). Data: fullR_phase_table.csv (qber_old, qber_fullR, qber_fullR_phase,
sinr_new) and zf_table.csv (model column).  Panel (b) (noise correlation of the sender-off captures NA1, NA2, NT1-3, N01)
is NOT regenerated: its values were never saved as a file (the paper text gives |rho| 0.53-0.54, 0.02-0.07 and 0.145).
The six model captures (N12A, N12B, N14A, N10A, N12C, N08A) were identified by matching the crosses of the original PNG."""
import csv
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
T={r["tag"]:r for r in csv.DictReader(open("fullR_phase_table.csv")) if r["tag"].startswith("N")}
M={r["run"]:float(r["model"]) for r in csv.DictReader(open("zf_table.csv"))}
fig,a=plt.subplots(figsize=(4.8,3.4),dpi=200)
x=lambda k:[float(T[t]["sinr_new"]) for t in T]; q=lambda k:[100*float(T[t][k]) for t in T]
a.plot(x(0),q("qber_old"),"o",mfc="none",color="gray",ms=4,label="diagonal-noise MMSE")
a.plot(x(0),q("qber_fullR"),"s",mfc="none",color="#1f6fb4",ms=4,label="+ full covariance R")
a.plot(x(0),q("qber_fullR_phase"),"o",color="#1f6fb4",ms=4,label="+ blind phase correction")
six=["N12A","N12B","N14A","N10A","N12C","N08A"]
a.plot([float(T[t]["sinr_new"]) for t in six],[M[t] for t in six],"kx",ms=5,label="model (Theorem 1, matched R)")
a.axhline(6.55,color="#c0392b",ls="--",lw=1); a.text(20,7,"6.55%",color="#c0392b",fontsize=7)
a.set_xlabel("measured post-MMSE SINR (dB)"); a.set_ylabel("QBER (%)"); a.set_title("(a) QBER of the three decoders",fontsize=9); a.legend(fontsize=6,frameon=False)
plt.tight_layout(); plt.savefig("regenerated/fig_dec_a.png")
