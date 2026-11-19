import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import norm
from scipy.optimize import brentq
h=lambda q: 0 if q<=0 or q>=1 else -q*np.log2(q)-(1-q)*np.log2(1-q)
r=lambda q,f: max(0,1-(1+f)*h(q))
Q=lambda s:norm.sf(np.sqrt(2*10**(s/10)))
qA=lambda G:Q(G-4.58); qB=lambda G:Q(G+1.0)
for f in (1.0,1.16):
    qth=brentq(lambda q:1-(1+f)*h(q),1e-4,.2)
    print('f',f,'Q_th %.4f'%qth,'G_th A %.2f B %.2f'%(brentq(lambda G:qA(G)-qth,-10,30),brentq(lambda G:qB(G)-qth,-10,30)))
print('G  QBER_A  r_A(f1.16)  QBER_B r_B | r_A(f1) r_B(f1)')
for G in (22,18,14,10,8,6,4,3):
    print(G,'%.4f %.3f  %.5f %.3f | %.3f %.3f'%(qA(G),r(qA(G),1.16),qB(G),r(qB(G),1.16),r(qA(G),1),r(qB(G),1)))
x=np.linspace(0,20,300)
fig,ax=plt.subplots(1,2,figsize=(9,3.5))
for q,l,c in ((qA,'A','C0'),(qB,'B','C1')):
    ax[0].semilogy(x,[q(v) for v in x],c,label='stream '+l)
    ax[1].plot(x,[r(q(v),1.16) for v in x],c,label=l+' f=1.16');ax[1].plot(x,[r(q(v),1.0) for v in x],c+'--',label=l+' f=1')
ax[0].axhline(.11,color='k',ls=':');ax[0].set_ylim(1e-6,.5);ax[0].set_xlabel('TX gain (dB)');ax[0].set_ylabel('QBER');ax[0].legend();ax[0].grid(alpha=.3,which='both')
ax[1].set_xlabel('TX gain (dB)');ax[1].set_ylabel('secret fraction per sifted bit');ax[1].legend(fontsize=7);ax[1].grid(alpha=.3)
fig.tight_layout();fig.savefig('skr.png',dpi=200)
