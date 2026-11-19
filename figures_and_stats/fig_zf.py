"""fig_zf.png: Theorem-1 QBER of MMSE (true and diagonal R) and ZF on random 2x2 channels, noise correlation 0.5.
(a) QBER vs nominal SNR at condition number 6;  (b) QBER vs condition number at 15 dB.  Mean over 12 random channels.
RE-CREATED from the description: the original script was not saved. Channel = U diag(s) V^H with random unitaries,
singular-value ratio = cond, ||H||_F^2 = 2, receive noise R = 10^(-SNR/10) [[1,.5],[.5,1]]. With seed 1 the values at 15 dB are
MMSE 5.7% / ZF 7.2% (cond 6) and 23% / 35% (cond 20), against 5.3 / 7.1 and 21 / 36 in the paper text: same curves, not identical numbers."""
import sys; import os; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","model_ZF"))
import numpy as np, zfmodel as z
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
def chan(k,rng):
    U,_=np.linalg.qr(rng.normal(size=(2,2))+1j*rng.normal(size=(2,2))); V,_=np.linalg.qr(rng.normal(size=(2,2))+1j*rng.normal(size=(2,2)))
    s=np.array([k,1.0]); s=s*np.sqrt(2)/np.linalg.norm(s); return U@np.diag(s)@V.conj().T
def avg(k,snr,n=12,seed=1,rho=.5):
    rng=np.random.default_rng(seed); N=10**(-snr/10); R=N*np.array([[1,rho],[rho,1]]); Rd=np.diag(np.diag(R)); out=[]
    for _ in range(n):
        H=chan(k,rng); e=z.eqs(H,R); ed=z.eqs(H,Rd)
        out.append((z.qber(e["MMSE"],H,R),z.qber(ed["MMSE"],H,R),z.qber(e["ZF"],H,R)))
    return np.maximum(np.mean(out,0),1e-5)
snr=list(range(0,31,3)); A=np.array([avg(6,s) for s in snr]); ks=[1.5,2,3,4,6,9,13,20]; B=np.array([avg(k,15) for k in ks])
fig,ax=plt.subplots(1,2,figsize=(9.4,3.4),dpi=200)
for a,x,D,xl,t in ((ax[0],snr,A,"nominal SNR (dB)","(a) cond(H)=6, noise corr. 0.5"),(ax[1],ks,B,"condition number of H","(b) SNR 15 dB")):
    a.semilogy(x,D[:,0],"k-o",ms=3,label="MMSE (true R)")
    if a is ax[0]: a.semilogy(x,D[:,1],"--s",color="#1f77b4",ms=3,label="MMSE (diag R)")
    a.semilogy(x,D[:,2],"-^",color="#d62728",ms=3,label="ZF"); a.axhline(.0655,color="gray",ls=":")
    a.set_xlabel(xl); a.set_title(t,fontsize=9); a.legend(fontsize=7)
ax[0].set_ylabel("QBER"); plt.tight_layout(); plt.savefig("regenerated/fig_zf.png")
print("15 dB, cond 6:",avg(6,15),"cond 20:",avg(20,15))
