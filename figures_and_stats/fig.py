import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import norm
g=np.array([14,10,8,6,4.]);n=np.array([22176,22176,21888,22176,20160])
A=np.array([1,70,364,985,1887])/n; B=np.array([0,0,3,13,73])/n
x=np.linspace(2,24,200); Q=lambda s:norm.sf(np.sqrt(2*10**(s/10)))
fig,ax=plt.subplots(figsize=(6.2,3.8))
ax.semilogy(x,Q(x-4.58),'C0-',label='A fit: SNR = G - 4.6 dB');ax.semilogy(x,Q(x+1.0),'C1-',label='B fit: SNR = G + 1.0 dB')
ax.semilogy(g,np.maximum(A,1e-6),'C0o');ax.semilogy(g,np.maximum(B,1e-6),'C1s')
ax.set_ylim(1e-6,0.5);ax.set_xlabel('TX gain G (dB)');ax.set_ylabel('BER (MMSE)');ax.grid(alpha=.3,which='both');ax.legend()
ax.set_title('BPSK/AWGN fit to measured 2x2 MMSE BER (points at 1e-6 = 0 errors)',fontsize=8)
fig.tight_layout();fig.savefig('ber_fit.png',dpi=200)
