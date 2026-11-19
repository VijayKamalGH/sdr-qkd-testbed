import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import norm
G=np.array([14,10,8,6,5,4.]); Q=np.array([2.46,4.59,9.28,12.68,17.65,20.05])/100
h=lambda q:-q*np.log2(q)-(1-q)*np.log2(1-q)
snr=norm.isf(Q)**2/2; sdb=10*np.log10(snr); print('eff SNR dB',np.round(sdb,2),'offset',np.round(sdb-G,2))
for f in (1.16,1.0): print('f',f,'asympt r',[round(max(0,1-(1+f)*h(q)),3) for q in Q])
m=G<=10; c=np.mean(sdb[m]-G[m]); print('offset fit (G<=10)',round(c,2))
x=np.linspace(3,16,200); mod=norm.sf(np.sqrt(2*10**((x+c)/10)))
fig,ax=plt.subplots(1,2,figsize=(9,3.5))
ax[0].semilogy(x,mod,'C0-',label='BPSK/AWGN fit, SNR = G %+.1f dB (G<=10 points)'%c); ax[0].semilogy(G,Q,'ko',label='measured SDR QKD (real RF)')
ax[0].semilogy([30],[1e-4],'k^',label='G=30: 0 errors (<7e-5)'); ax[0].axhline(.11,color='r',ls=':',label='BB84 11% limit'); ax[0].set_ylim(5e-5,.5)
ax[0].set_xlabel('TX gain (dB)');ax[0].set_ylabel('QBER'); ax[0].grid(alpha=.3,which='both'); ax[0].legend(fontsize=6.5)
qq=np.linspace(0.001,.12,200); ax[1].plot(qq*100,[max(0,1-2.16*h(q)) for q in qq],'C1',label='f=1.16'); ax[1].plot(qq*100,[max(0,1-2*h(q)) for q in qq],'C1--',label='f=1.0')
ax[1].plot(Q*100,[max(0,1-2.16*h(q)) for q in Q],'ko'); ax[1].set_xlabel('QBER (%)'); ax[1].set_ylabel('asymptotic secret fraction'); ax[1].grid(alpha=.3); ax[1].legend(fontsize=7)
fig.tight_layout(); fig.savefig('qkd_sweep.png',dpi=200)
