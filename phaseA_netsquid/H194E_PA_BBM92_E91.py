import argparse, math, numpy as np
from H194E_PA_CLASSICAL_LINK import ClassicalLink
from H194E_PA_BB84_SENDER_RECEIVER_EVE import h2

# Entangled-pair model: Werner state with visibility v (v=1-p for depolarising p), Eve intercept-resends the
# receiver's half on a fraction q in a random Z/X basis. For measurement angles a,b (x-z plane) the correlator is
#   E(a,b) = v*cos(a-b)*(1-q/2)      [Eve averaged over Z/X: product-state term = v*cos(a-b)/2]
def corr(a, b, v, q): return v*np.cos(a-b)*(1-q/2)
def outcomes(a, b, v, q, rs):
    x = rs.integers(0,2,len(a)); eq = rs.random(len(a)) < (1+corr(a,b,v,q))/2
    return x, np.where(eq, x, 1-x)                      # sender bit, receiver bit (marginals uniform)

def finite_key(ks, kr, link, rs, eps=1e-6, f_ec=1.16, abort=0.11):
    nk = len(ks); idx = rs.permutation(nk); nt = int(0.1*nk); t, rest = idx[:nt], idx[nt:]
    link.send(2*nt)
    Qh = float(np.mean(ks[t]!=kr[t])); Qup = Qh+math.sqrt(math.log(1/eps)/(2*nt))
    Qt = float(np.mean(ks[rest]!=kr[rest]))
    if Qup > abort: return Qh, Qup, 0
    lec = f_ec*h2(Qt)*len(rest); link.send(int(lec))
    return Qh, Qup, max(0, math.floor(len(rest)*(1-h2(Qup))-lec-2*math.log2(1/eps)))

def bbm92(n, v, q, seed, link):                         # bases Z (0) / X (pi/2), same-basis rounds -> key
    rs = np.random.default_rng(seed)
    a = rs.integers(0,2,n)*np.pi/2; b = rs.integers(0,2,n)*np.pi/2
    s, r = outcomes(a, b, v, q, rs); link.send(n); link.send(n)
    keep = a == b
    return finite_key(s[keep], r[keep], link, rs)

def e91(n, v, q, seed, link):                           # CHSH settings; key from the matching (a=b) pair
    rs = np.random.default_rng(seed)
    A = np.array([0, np.pi/2, np.pi/4]); B = np.array([np.pi/4, 0, -np.pi/4])   # a1,a2,a3 / b1,b2,b3 (Ekert)
    ia, ib = rs.integers(0,3,n), rs.integers(0,3,n)
    a, b = A[ia], B[ib]
    s, r = outcomes(a, b, v, q, rs); link.send(n); link.send(n)
    def E(i, j):
        m = (ia==i)&(ib==j); return np.mean((1-2*s[m])*(1-2*r[m]))
    S = abs(E(0,0)+E(0,2)+E(1,0)-E(1,2))                # a=0,a'=pi/2 ; b=pi/4,b'=-pi/4
    keep = np.isclose(a, b)                             # equal-angle pairs (0 and pi/4) give the key
    ks, kr = s[keep], r[keep]
    out = finite_key(ks, kr, link, rs) if len(ks) > 100 else (1.0, 1.0, 0)
    return S, out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=69632)
    ap.add_argument("--vis", type=float, default=1.0); ap.add_argument("--p-loss", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1); a = ap.parse_args()
    print("BBM92"); print(f"{'q':>5} {'Q_pred':>7} {'Qhat':>7} {'Qup':>7} {'key':>7}")
    for q in (0,0.25,0.5,1.0):
        Qh,Qup,k = bbm92(a.n,a.vis,q,a.seed,ClassicalLink(p_loss=a.p_loss,seed=a.seed))
        print(f"{q:5.2f} {(1-a.vis*(1-q/2))/2*100:6.2f}% {Qh*100:6.2f}% {Qup*100:6.2f}% {k:7d}")
    print("E91 (CHSH)"); print(f"{'q':>5} {'S_pred':>7} {'S':>7} {'verdict':>10} {'Qhat':>7} {'key':>7}")
    for q in (0,0.25,0.5,1.0):
        S,(Qh,Qup,k) = e91(a.n,a.vis,q,a.seed,ClassicalLink(p_loss=a.p_loss,seed=a.seed))
        print(f"{q:5.2f} {2*math.sqrt(2)*a.vis*(1-q/2):7.3f} {S:7.3f} {'secure' if S>2 else 'EVE/noise':>10} {Qh*100:6.2f}% {k:7d}")
