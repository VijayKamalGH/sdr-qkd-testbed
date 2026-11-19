import argparse, glob, json, re, math, numpy as np
from H194E_PA_CLASSICAL_LINK import ClassicalLink
# Each normal-channel SDR capture -> one hybrid run. Channel noise from the SDR QBER (p_dep = 2*QBER, since a
# depolarising prob p gives bit-flip prob p/2), n = decoded qubits, classical loss = 1 - frames/256.
ap = argparse.ArgumentParser()
ap.add_argument("--engine", choices=["numpy", "netsquid"], default="numpy")
ap.add_argument("--glob", default="H194E_V18Z34_N*_fullR_ph_qkd.json")
ap.add_argument("--q-eve", type=float, default=0.0); ap.add_argument("--seed", type=int, default=1)
a = ap.parse_args()
if a.engine == "numpy":
    from H194E_PA_BB84_SENDER_RECEIVER_EVE import run as run_np
    def hybrid(n, qber, link, q): return run_np(n, q, qber, a.seed, link)          # qch = SDR QBER
else:
    import netsquid as ns
    from H194E_PA_BB84_NETSQUID import run as run_ns
    def hybrid(n, qber, link, q): return run_ns(n, q, 2*qber, a.seed, link)
print(f"{'run':6s} {'frames':>6s} {'loss':>6s} {'SDR Q':>7s} {'SDR key':>8s} | {'hyb Qhat':>8s} {'hyb key':>8s} {'t_cls(s)':>8s}")
rows = []
for f in sorted(glob.glob(a.glob)):
    d = json.load(open(f)); tag = re.search(r"_(N\d+[A-Z])_", f).group(1)
    n = int(d["qubits"]); loss = max(0.0, 1 - d["frames"]/256); qb = float(d["qber"])
    link = ClassicalLink(p_loss=loss, seed=a.seed)
    r = hybrid(n, qb, link, a.q_eve)
    sdr_key = 0 if d.get("abort") else int(d.get("final_bits") or 0)
    rows.append((tag, sdr_key, r["key"]))
    print(f"{tag:6s} {d['frames']:6d} {loss:6.3f} {qb*100:6.2f}% {sdr_key:8d} | {r['Qhat']*100:7.2f}% {r['key']:8d} {link.time:8.2f}", flush=True)
ok = sum(1 for _, s, h in rows if (s > 0) == (h > 0))
print(f"\nSDR and hybrid agree on key/abort in {ok} of {len(rows)} runs")
