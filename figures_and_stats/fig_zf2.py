"""fig_zf2.png: measured QBER against the matched model (MMSE+R+phi and ZF) and the ZF/MMSE ratio, 15 captures.
Data: zf_table.csv (the values printed in Table tab:zf of the paper). Exact regeneration of the figure."""
import csv, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
R=list(csv.DictReader(open("zf_table.csv")))
f=lambda k:np.array([float(r[k]) for r in R])
fig,ax=plt.subplots(1,2,figsize=(9,3.3),dpi=200)
ax[0].plot([0,40],[0,40],"k:",lw=.8)
ax[0].plot(f("model"),f("mmse_R_phi"),"o",color="#1f77b4",ms=4,label="MMSE + full R + phase")
ax[0].plot(f("zf_model"),f("zf"),"^",color="#d62728",ms=4,label="ZF")
ax[0].set_xlabel("model QBER (%)"); ax[0].set_ylabel("measured QBER (%)"); ax[0].set_title("(a) Model versus measurement",fontsize=9); ax[0].legend(fontsize=7)
ax[1].bar(range(len(R)),f("zf_over_mmse"),color="gray"); ax[1].axhline(1,color="k",lw=.8)
ax[1].set_xticks(range(len(R))); ax[1].set_xticklabels([r["run"] for r in R],rotation=70,fontsize=7)
ax[1].set_ylabel("ZF QBER / MMSE QBER"); ax[1].set_title("(b) Measured ratio per capture",fontsize=9)
plt.tight_layout(); plt.savefig("regenerated/fig_zf2.png")
