import numpy as np, csv
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
rng=np.random.default_rng(1); S2=2**-.5
VEC={(0,0):(1,0),(0,1):(0,1),(1,0):(S2,S2),(1,1):(S2,-S2)}
def pred(sa,sb,n=100000):
    va,vb=[1/(2*10**(x/10)) for x in (sa,sb)]
    b=rng.integers(0,2,n); v=rng.integers(0,2,n)
    s=np.array([VEC[(int(x),int(y))] for x,y in zip(b,v)])
    z1=s[:,0]+rng.normal(0,np.sqrt(va),n); z2=s[:,1]+rng.normal(0,np.sqrt(vb),n)
    bit=np.where(b==0,abs(z2)>abs(z1),z1*z2<0); return np.mean(bit!=v)
R=[r for r in csv.DictReader(open('tbl.csv')) if r['tag'][0]=='N']
gain={'N30':30,'N14':14,'N12':12,'N10':10,'N08':8,'N06':6,'N04':4,'N02':2}
fig,ax=plt.subplots(1,2,figsize=(9.2,3.7),dpi=200)
BL="#1f4e8c"; GR="#8a96a3"
for r in R:
    g=gain[r['tag'][:3]]; q=float(r['qber']); s=float(r['sinr_mean'])
    late = r['tag'] in ('N12C','N12D')
    ax[0].plot(g,max(q,1e-4),"o",color="#c0392b" if late else BL,ms=5)
    ax[1].plot(s,max(q,1e-4),"o",color="#c0392b" if late else BL,ms=5)
    if q>0 and s<20: ax[1].plot(s,pred(float(r['sinr_a']),float(r['sinr_b'])),"x",color=GR,ms=5)
ax[0].plot([],[],"o",color=BL,label="captures"); ax[0].plot([],[],"o",color="#c0392b",label="12 dB repeats (later)")
ax[1].plot([],[],"o",color=BL,label="measured"); ax[1].plot([],[],"x",color=GR,label="model from measured SINR")
for a,xl in zip(ax,["nominal TX gain (dB)","measured post-MMSE SINR, mean of 2 streams (dB)"]):
    a.set_yscale("log"); a.set_ylim(5e-5,0.5); a.axhline(0.11,color="#c0392b",ls=":",lw=1.2)
    a.set_xlabel(xl); a.set_ylabel("QBER"); a.grid(alpha=.25); a.legend(fontsize=7,frameon=False,loc="lower left")
ax[0].text(16,0.125,"11% limit",color="#c0392b",fontsize=7)
ax[0].set_title("a) vs nominal gain: repeats disagree",fontsize=8); ax[1].set_title("b) vs measured SINR: points collapse",fontsize=8)
plt.tight_layout(); plt.savefig("qber_vs_sinr.png")
