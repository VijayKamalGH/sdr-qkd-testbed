#!/usr/bin/env python3
"""Phase A, lab-PC version: quantum channel in NetSquid, classical channel = SDR-derived ClassicalLink.
UNTESTED in the sandbox (NetSquid not installed there). Run in the netsquid310 environment.
Same finite-key code path as the numpy driver, so results should match it within sampling error."""
import argparse, math, numpy as np
import netsquid as ns
import netsquid.qubits.qubitapi as qapi
from netsquid.qubits import ketstates as ks
from H194E_PA_CLASSICAL_LINK import ClassicalLink
from H194E_PA_BB84_SENDER_RECEIVER_EVE import h2

def prep(bit, basis):
    q = qapi.create_qubits(1)[0]
    qapi.assign_qstate([q], ks.s1 if bit else ks.s0)       # |0>, |1>
    if basis: qapi.operate(q, ns.H)                        # |+>, |->
    return q
def meas(q, basis):
    if basis: qapi.operate(q, ns.H)
    return int(qapi.measure(q, observable=ns.Z)[0])

def run(n, q_eve, p_dep, seed, link, eps=1e-6, f_ec=1.16):
    ns.set_random_state(seed); rs = np.random.default_rng(seed)
    sb, sx, rx = rs.integers(0,2,n), rs.integers(0,2,n), rs.integers(0,2,n)
    res = np.zeros(n, int)
    for i in range(n):
        qb = prep(sb[i], sx[i])
        if rs.random() < q_eve:                            # Eve: intercept-resend
            ex = rs.integers(0,2); b = meas(qb, ex); qb = prep(b, ex)
        qapi.depolarize(qb, p_dep)                         # channel noise
        res[i] = meas(qb, rx[i])
    link.send(n); link.send(n)
    keep = rx == sx; k1, k2 = sb[keep], res[keep]; nk = len(k1)
    idx = rs.permutation(nk); nt = int(0.1*nk); t, rest = idx[:nt], idx[nt:]
    link.send(2*nt)
    Qhat = float(np.mean(k1[t] != k2[t])); Qup = Qhat + math.sqrt(math.log(1/eps)/(2*nt))
    Qtrue = float(np.mean(k1[rest] != k2[rest]))
    if Qup > 0.11: return dict(q=q_eve, Qhat=Qhat, Qup=Qup, key=0, aborted=True)
    lec = f_ec*h2(Qtrue)*len(rest); link.send(int(lec))
    L = max(0, math.floor(len(rest)*(1-h2(Qup)) - lec - 2*math.log2(1/eps)))
    return dict(q=q_eve, Qhat=Qhat, Qup=Qup, key=L, aborted=L == 0)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--p-dep", type=float, default=0.0)   # depolarise prob p -> bit-flip prob p/2 in Z and X
    ap.add_argument("--p-loss", type=float, default=0.0); ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    for q in (0, 0.25, 0.5, 1.0):
        print(run(a.n, q, a.p_dep, a.seed, ClassicalLink(p_loss=a.p_loss, seed=a.seed)))
