import argparse, math, numpy as np
import netsquid as ns
import netsquid.qubits.qubitapi as qapi
from H194E_PA_CLASSICAL_LINK import ClassicalLink

# Two-step QSDC with real Bell pairs. Leg 1: receiver -> sender (Eve may intercept-resend, noise p).
# Check pairs: both halves measured in a common random Z/X basis. Data pairs: sender applies Z^b1 X^b2, leg 2 (noise p),
# receiver Bell-measures (CNOT, H, measure) and reads (b1, b2) directly.
def bell_pair():
    a, b = qapi.create_qubits(2)
    qapi.operate(a, ns.H); qapi.operate([a, b], ns.CNOT)
    return a, b
def prep_basis(bit, basis):
    q = qapi.create_qubits(1)[0]
    qapi.assign_qstate([q], ns.qubits.ketstates.s1 if bit else ns.qubits.ketstates.s0)
    if basis: qapi.operate(q, ns.H)
    return q
def mz(q, basis):
    if basis: qapi.operate(q, ns.H)
    return int(qapi.measure(q, observable=ns.Z)[0])
def leg1(b, q_eve, p, rs):
    if rs.random() < q_eve:
        ex = rs.integers(0, 2); r = mz(b, ex); b = prep_basis(r, ex)
    qapi.depolarize(b, p)
    return b

def run(msg, q_eve, p, seed, link, rep=3, check_min=4000, eps=1e-6, thr=0.11):
    ns.set_random_state(seed); rs = np.random.default_rng(seed)
    coded = np.repeat(msg, rep); n_data = (len(coded)+1)//2
    nc = max(int(math.ceil(0.1*n_data/0.9)), check_min)
    err = 0
    for _ in range(nc):                                   # security check
        a, b = bell_pair(); b = leg1(b, q_eve, p, rs); bs = rs.integers(0, 2)
        err += mz(a, bs) != mz(b, bs)
    Qh = err/nc; Qup = Qh + math.sqrt(math.log(1/eps)/(2*nc))
    link.send(4*nc)
    if Qup > thr: return dict(aborted=True, Qcheck=Qh, ber_raw=None, ber=None, ok=False)
    pad = np.concatenate([coded, np.zeros(2*n_data-len(coded), int)]).reshape(-1, 2); rec = []
    for b1, b2 in pad:
        a, b = bell_pair(); b = leg1(b, q_eve, p, rs)
        if b2: qapi.operate(b, ns.X)
        if b1: qapi.operate(b, ns.Z)
        qapi.depolarize(b, p)                              # leg 2
        qapi.operate([a, b], ns.CNOT); qapi.operate(a, ns.H)
        rec += [int(qapi.measure(a, observable=ns.Z)[0]), int(qapi.measure(b, observable=ns.Z)[0])]
    link.send(n_data)
    rec = np.array(rec[:len(coded)]); maj = (rec.reshape(-1, rep).sum(1) > rep/2).astype(int)
    ber_raw = float(np.mean(rec != coded)); ber = float(np.mean(maj != msg))
    return dict(aborted=False, Qcheck=Qh, ber_raw=ber_raw, ber=ber, ok=bool(ber == 0))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--bits", type=int, default=1000)
    ap.add_argument("--p-dep", type=float, default=0.0); ap.add_argument("--p-loss", type=float, default=0.0)
    ap.add_argument("--rep", type=int, default=3); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--check-min", type=int, default=4000); a = ap.parse_args()
    msg = np.random.default_rng(99).integers(0, 2, a.bits)
    print(f"{'q':>5} {'Qcheck':>7} {'verdict':>8} {'raw BER':>8} {'BER':>7} {'delivered':>9}")
    for q in (0, 0.1, 0.25, 0.5, 1.0):
        r = run(msg, q, a.p_dep, a.seed, ClassicalLink(p_loss=a.p_loss, seed=a.seed), rep=a.rep, check_min=a.check_min)
        if r["aborted"]: print(f"{q:5.2f} {r['Qcheck']*100:6.2f}% {'ABORT':>8} {'-':>8} {'-':>7} {'no':>9}", flush=True)
        else: print(f"{q:5.2f} {r['Qcheck']*100:6.2f}% {'pass':>8} {r['ber_raw']*100:7.2f}% {r['ber']*100:6.2f}% {str(r['ok']):>9}", flush=True)
