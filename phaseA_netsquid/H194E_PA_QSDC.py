import argparse, math, numpy as np
from H194E_PA_CLASSICAL_LINK import ClassicalLink

# Two-step QSDC (Deng-Long-Liu type), model level.
# Leg 1: receiver -> sender carries one half of each Bell pair. Eve (intercept-resend, fraction q, random Z/X basis)
#        may touch it. A random 10% of pairs are check pairs: both halves measured in a common random Z/X basis
#        (same law as BBM92: Qcheck = (1 - v(1-q/2))/2). If Qcheck_up > thr: abort, nothing is encoded.
# Leg 2: sender applies one of 4 Paulis (2 message bits) and returns the qubit; receiver Bell-measures.
#        Depolarising prob p per leg (v = 1-p). An intercepted pair gives a uniformly random Bell result.
def h2(x): return 0.0 if x<=0 or x>=1 else -x*math.log2(x)-(1-x)*math.log2(1-x)

def run(msg_bits, q, p, seed, link, rep=3, eps=1e-6, thr=0.11, check_frac=0.1, check_min=4000):
    rs = np.random.default_rng(seed)
    coded = np.repeat(msg_bits, rep)                         # repetition code
    n_data = (len(coded)+1)//2
    nc = max(int(math.ceil(check_frac*n_data/(1-check_frac))), check_min); n = n_data + nc
    v = 1 - p
    # ---- security check on nc pairs
    Qc_true = (1 - v*(1-q/2))/2
    errs = rs.random(nc) < Qc_true
    Qh = errs.mean() if nc else 1.0; Qup = Qh + math.sqrt(math.log(1/eps)/(2*max(nc,1)))
    link.send(nc*2); link.send(nc*2)
    if Qup > thr: return dict(aborted=True, Qcheck=Qh, Qup=Qup, ber=None, ok=False, pairs=n)
    # ---- encoding and Bell measurement on n_data pairs
    pad = np.concatenate([coded, np.zeros(2*n_data-len(coded), int)]).reshape(-1, 2)
    sym = pad[:,0]*2 + pad[:,1]                              # Bell index 0..3
    hit = rs.random(n_data) < q
    # depolarising on each leg: a depolarised leg gives a uniform Bell result (both bits random)
    dep = (rs.random(n_data) < p) | (rs.random(n_data) < p)
    b1, b2 = sym//2, sym%2
    rnd = rs.integers(0,4,n_data); b1 = np.where(dep, rnd//2, b1); b2 = np.where(dep, rnd%2, b2)
    # intercept-resend (Eve measures in Z or X, resends): pair becomes a product state, so exactly ONE message bit
    # (sign bit for Z, parity bit for X) is randomised and the other is unchanged
    eh = hit & ~dep; pos = rs.integers(0,2,n_data); rb = rs.integers(0,2,n_data)
    b1 = np.where(eh & (pos == 0), rb, b1); b2 = np.where(eh & (pos == 1), rb, b2)
    rec = np.stack([b1, b2], 1).reshape(-1)[:len(coded)]
    maj = (rec.reshape(-1, rep).sum(1) > rep/2).astype(int)
    ber_raw = float(np.mean(rec != coded)); ber = float(np.mean(maj != msg_bits))
    link.send(n_data)                                         # receiver's classical acknowledgement
    return dict(aborted=False, Qcheck=Qh, Qup=Qup, ber_raw=ber_raw, ber=ber, ok=bool(ber == 0), pairs=n)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--bits", type=int, default=2000)
    ap.add_argument("--p", type=float, default=0.0); ap.add_argument("--p-loss", type=float, default=0.0)
    ap.add_argument("--rep", type=int, default=3); ap.add_argument("--seed", type=int, default=1); ap.add_argument("--check-min", type=int, default=4000); a = ap.parse_args()
    msg = np.random.default_rng(99).integers(0,2,a.bits)
    print(f"{'q':>5} {'Qcheck':>7} {'verdict':>8} {'raw BER':>8} {'BER':>7} {'delivered':>9} {'pairs':>6} {'t_cls(s)':>8}")
    for q in (0, 0.1, 0.25, 0.5, 1.0):
        link = ClassicalLink(p_loss=a.p_loss, seed=a.seed)
        r = run(msg, q, a.p, a.seed, link, rep=a.rep, check_min=a.check_min)
        if r["aborted"]: print(f"{q:5.2f} {r['Qcheck']*100:6.2f}% {'ABORT':>8} {'-':>8} {'-':>7} {'no':>9} {r['pairs']:6d} {link.time:8.2f}")
        else: print(f"{q:5.2f} {r['Qcheck']*100:6.2f}% {'pass':>8} {r['ber_raw']*100:7.2f}% {r['ber']*100:6.2f}% {str(r['ok']):>9} {r['pairs']:6d} {link.time:8.2f}")
