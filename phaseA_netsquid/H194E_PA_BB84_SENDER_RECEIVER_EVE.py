#!/usr/bin/env python3
"""Phase A BB84 driver: Sender, Receiver, optional Eve (intercept-resend, fraction q).
Quantum channel = numpy model (depolarising flip prob q_ch) -- same QBER law as the SDR emulation.
Classical channel = H194E_PA_CLASSICAL_LINK (SDR-derived). Finite-key rule as in the paper."""
import argparse, json, math, numpy as np
from H194E_PA_CLASSICAL_LINK import ClassicalLink

def h2(x): return 0.0 if x<=0 or x>=1 else -x*math.log2(x)-(1-x)*math.log2(1-x)

def run(n, q, qch, seed, link, f_ec=1.16, eps=1e-6, test_frac=0.10, abort=0.11):
    rs = np.random.default_rng(seed)
    # Sender
    sb, sx = rs.integers(0,2,n), rs.integers(0,2,n)          # bit, basis
    # Eve (intercept-resend on fraction q of qubits, random basis)
    bit, bas = sb.copy(), sx.copy()
    hit = rs.random(n) < q
    eb = rs.integers(0,2,n)
    flip = (eb != sx) & hit & (rs.random(n) < 0.5)           # wrong basis -> random result
    bit = np.where(hit, np.where(eb == sx, sb, rs.integers(0,2,n)), sb)
    # channel noise
    bit = bit ^ (rs.random(n) < qch)
    # Receiver
    rb = rs.integers(0,2,n)
    res = np.where(rb == sx, bit, rs.integers(0,2,n))
    # classical: bases exchanged (n bits each way)
    link.send(n); link.send(n)
    keep = rb == sx
    ks, kr = sb[keep], res[keep]; nk = keep.sum()
    # test subset
    idx = rs.permutation(nk); nt = int(test_frac*nk)
    t, rest = idx[:nt], idx[nt:]
    link.send(nt); link.send(nt)
    Qhat = float(np.mean(ks[t] != kr[t])) if nt else 1.0
    Qup = Qhat + math.sqrt(math.log(1/eps)/(2*nt))
    nkey = len(rest); Qtrue = float(np.mean(ks[rest] != kr[rest]))
    if Qup > abort: return dict(q=q,Qhat=Qhat,Qup=Qup,Qtrue=Qtrue,key=0,aborted=True,time=link.time,nt=nt)
    lec = f_ec*h2(Qtrue)*nkey                                  # reconciliation leakage (Cascade-like)
    link.send(int(lec))
    L = max(0, math.floor(nkey*(1-h2(Qup)) - lec - 2*math.log2(1/eps)))
    return dict(q=q,Qhat=Qhat,Qup=Qup,Qtrue=Qtrue,key=L,aborted=L==0,time=link.time,nt=nt)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=69632); ap.add_argument("--qch", type=float, default=0.0)
    ap.add_argument("--p-loss", type=float, default=0.0); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--q-list", type=float, nargs="+", default=[0,0.25,0.5,1.0])
    ap.add_argument("--json", default=None)
    a = ap.parse_args(); out = []
    print(f"{'q':>5} {'Q_pred':>7} {'Qhat':>7} {'Qup':>7} {'key':>7} {'abort':>6} {'t_cls(s)':>9}")
    for q in a.q_list:
        link = ClassicalLink(p_loss=a.p_loss, seed=a.seed)
        r = run(a.n, q, a.qch, a.seed, link); out.append(r)
        pred = a.qch + q/4*(1-2*a.qch)
        print(f"{q:5.2f} {pred*100:6.2f}% {r['Qhat']*100:6.2f}% {r['Qup']*100:6.2f}% {r['key']:7d} {str(r['aborted']):>6} {r['time']:9.1f}")
    if a.json: json.dump(out, open(a.json,"w"), indent=1)
