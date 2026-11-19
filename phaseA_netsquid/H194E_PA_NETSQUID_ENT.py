import argparse, math, numpy as np
import netsquid as ns
import netsquid.qubits.qubitapi as qapi
from netsquid.qubits import operators as ops
from H194E_PA_CLASSICAL_LINK import ClassicalLink
from H194E_PA_BBM92_E91 import finite_key

def bell_pair():
    a, b = qapi.create_qubits(2)
    qapi.operate(a, ns.H); qapi.operate([a, b], ns.CNOT)      # |Phi+>
    return a, b
def measure_angle(q, ang):                                    # projective measurement along angle ang in the x-z plane
    if abs(ang) > 1e-12: qapi.operate(q, ops.create_rotation_op(-ang, (0, 1, 0)))
    return int(qapi.measure(q, observable=ns.Z)[0])
def prep_basis(bit, basis):
    q = qapi.create_qubits(1)[0]
    qapi.assign_qstate([q], ns.qubits.ketstates.s1 if bit else ns.qubits.ketstates.s0)
    if basis: qapi.operate(q, ns.H)
    return q

def one_round(ang_a, ang_b, p, q_eve, rs):
    a, b = bell_pair()
    if rs.random() < q_eve:                                   # Eve intercepts Bob's half, resends
        ex = rs.integers(0, 2); r = measure_angle(b, ex*np.pi/2); b = prep_basis(r, ex)
    qapi.depolarize(b, p)
    return measure_angle(a, ang_a), measure_angle(b, ang_b)

def bbm92(n, p, q, seed, link):
    ns.set_random_state(seed); rs = np.random.default_rng(seed)
    a = rs.integers(0, 2, n)*np.pi/2; b = rs.integers(0, 2, n)*np.pi/2
    s = np.zeros(n, int); r = np.zeros(n, int)
    for i in range(n): s[i], r[i] = one_round(a[i], b[i], p, q, rs)
    link.send(n); link.send(n); keep = a == b
    return finite_key(s[keep], r[keep], link, rs)

def e91(n, p, q, seed, link):
    ns.set_random_state(seed); rs = np.random.default_rng(seed)
    A = np.array([0, np.pi/2, np.pi/4]); B = np.array([np.pi/4, 0, -np.pi/4])
    ia, ib = rs.integers(0, 3, n), rs.integers(0, 3, n)
    s = np.zeros(n, int); r = np.zeros(n, int)
    for i in range(n): s[i], r[i] = one_round(A[ia[i]], B[ib[i]], p, q, rs)
    link.send(n); link.send(n)
    def E(i, j):
        m = (ia == i) & (ib == j); return np.mean((1-2*s[m])*(1-2*r[m]))
    S = abs(E(0,0)+E(0,2)+E(1,0)-E(1,2))
    keep = np.isclose(A[ia], B[ib])
    out = finite_key(s[keep], r[keep], link, rs) if keep.sum() > 100 else (1.0, 1.0, 0)
    return S, out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--p-dep", type=float, default=0.0); ap.add_argument("--p-loss", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1); a = ap.parse_args()
    v = 1 - a.p_dep
    print("BBM92 (NetSquid)"); print(f"{'q':>5} {'Q_pred':>7} {'Qhat':>7} {'key':>7}")
    for q in (0, 0.25, 0.5, 1.0):
        Qh, Qup, k = bbm92(a.n, a.p_dep, q, a.seed, ClassicalLink(p_loss=a.p_loss, seed=a.seed))
        print(f"{q:5.2f} {(1-v*(1-q/2))/2*100:6.2f}% {Qh*100:6.2f}% {k:7d}", flush=True)
    print("E91 (NetSquid)"); print(f"{'q':>5} {'S_pred':>7} {'S':>7} {'Qhat':>7} {'key':>7}")
    for q in (0, 0.25, 0.5, 1.0):
        S, (Qh, Qup, k) = e91(a.n, a.p_dep, q, a.seed, ClassicalLink(p_loss=a.p_loss, seed=a.seed))
        print(f"{q:5.2f} {2*math.sqrt(2)*v*(1-q/2):7.3f} {S:7.3f} {Qh*100:6.2f}% {k:7d}", flush=True)
