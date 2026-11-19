import numpy as np
from scipy.stats import norm, multivariate_normal as mvn
VEC={("Z",0):(1,0),("Z",1):(0,1),("X",0):(1/2**.5,1/2**.5),("X",1):(1/2**.5,-1/2**.5)}
def P_opp(mu,S):                                   # Pr[x1 x2 < 0], x ~ N(mu,S)
    s=np.sqrt(np.diag(S)); a=mu/s; r=np.clip(S[0,1]/(s[0]*s[1]),-.999999,.999999)
    p2=mvn.cdf([-a[0],-a[1]],mean=[0,0],cov=[[1,r],[r,1]])
    return norm.cdf(-a[0])+norm.cdf(-a[1])-2*p2
def qber(W,H,R):
    """W: 2x2 complex equaliser (output scaled so decisions use Re part); phase offset ignored (corrected)."""
    M=(W@H).real; S=0.5*(W@R@W.conj().T).real; T=np.array([[1,1],[1,-1]])
    tot=0
    for (b,v),s in VEC.items():
        m=M@np.array(s)
        if b=="X": p=P_opp(m,S); e=p if v==0 else 1-p        # X0 correct if z1z2>0
        else:
            m2=T@m; S2=T@S@T.T; p=P_opp(m2,S2); e=p if v==0 else 1-p   # Z0 correct if |z1|>|z2| (uw>0)
        tot+=e
    return tot/4
def eqs(H,R):
    Ri=np.linalg.inv(R); A=H.conj().T@Ri@H; P=np.linalg.inv(np.eye(2)+A)
    W=P@H.conj().T@Ri; D=np.diag(1/np.real(np.diag(W@H)))
    return {"MMSE":D@W,"ZF":np.linalg.pinv(H),"ZFw":np.linalg.inv(A)@H.conj().T@Ri}
def sinrs(W,H,R):
    out=[]
    for k in range(2):
        g=W@H; sig=abs(g[k,k])**2; inter=abs(g[k,1-k])**2; noi=np.real(W[k]@R@W[k].conj())
        out.append(10*np.log10(sig/(inter+noi)))
    return out
