import numpy as np, csv
from math import erfc, sqrt, log2
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
Q=lambda x:0.5*erfc(x/sqrt(2))
h=lambda p:0 if p<=0 or p>=1 else -p*log2(p)-(1-p)*log2(1-p)
# gain: (QBER A, QBER B, key A, key B, rejected frames A,B, test bits A,B)
D={30:(0.0,0.0,22213,22213,0,0),
   14:(4.11,3.21,8744,11735,1,0),
   12:(2.37,1.82,13900,15542,1,0),
   10:(7.62,7.14,0,0,2,1),
   8:(7.86,9.29,0,0,6,10),
   6:(14.13,15.97,0,0,34,12),
   4:(18.22,20.54,0,0,36,49),
   2:(21.17,None,0,0,80,None)}
rows=[]
for g,(a,b,ka,kb,ra,rb) in sorted(D.items(),reverse=True):
    fit=Q(sqrt(2*10**((g-8.4)/10)))*100
    rows.append([g,a,b,round(fit,2),ka,kb,ra,rb])
with open("sweep_n.csv","w",newline="") as f:
    w=csv.writer(f);w.writerow("gain_dB,QBER_A_%,QBER_B_%,fit_%,key_A,key_B,rej_frames_A,rej_frames_B".split(","));w.writerows(rows)
for r in rows:print(r)
fig,ax=plt.subplots(1,2,figsize=(9,3.6),dpi=200)
g=np.array([r[0] for r in rows if r[0]<30])
ax[0].set_yscale("log")
gg=np.linspace(2,16,100)
ax[0].plot(gg,[Q(sqrt(2*10**((x-8.4)/10))) for x in gg],color="#9aa5b1",lw=1.5,label="BPSK/AWGN fit, SNR = G − 8.4 dB")
ax[0].plot([r[0] for r in rows if r[0]<30],[r[1]/100 for r in rows if r[0]<30],"o",color="#1f4e8c",ms=6,label="capture A")
ax[0].plot([r[0] for r in rows if r[0]<30 and r[2] is not None],[r[2]/100 for r in rows if r[0]<30 and r[2] is not None],"s",mfc="none",color="#1f4e8c",ms=6,label="capture B")
ax[0].plot([30],[1e-4],"^",color="k",ms=7,label="G=30: 0 errors")
ax[0].axhline(0.11,color="#c0392b",ls=":",lw=1.5); ax[0].text(15,0.125,"11% BB84 limit",color="#c0392b",fontsize=7)
ax[0].set_xlabel("TX gain (dB)");ax[0].set_ylabel("QBER");ax[0].set_ylim(5e-5,0.5)
ax[0].legend(fontsize=6.5,loc="lower left",frameon=False);ax[0].grid(alpha=.25)
qq=np.linspace(0.001,0.2,200)
ax[1].plot(qq*100,[max(0,1-h(q)-1.16*h(q)) for q in qq],color="#9aa5b1",lw=1.5,label="f = 1.16")
pts=[(r[1],) for r in rows]
for r in rows:
    for q in (r[1],r[2]):
        if q is not None: ax[1].plot(q,max(0,1-h(q/100)-1.16*h(q/100)),"o",color="#1f4e8c",ms=5)
ax[1].set_xlabel("QBER (%)");ax[1].set_ylabel("asymptotic secret fraction");ax[1].grid(alpha=.25);ax[1].legend(fontsize=7,frameon=False)
plt.tight_layout();plt.savefig("sweep_n.png")
