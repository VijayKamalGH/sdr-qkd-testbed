#!/usr/bin/env python3
"""Phase C1: Kalman tracking of the 2x2 channel on a capture. Compares per-frame pilot estimates (baseline analyser)
with a causal complex scalar Kalman filter per H entry (random-walk state, measurement = pilot estimate), then decodes
with the filtered H.  Usage: python3 H194E_PC_KALMAN.py --lib <dir with analyser> --tag KQ4 [--dir .] [--qmul 1] [--json out]"""
import argparse, json, os, sys
from pathlib import Path
import numpy as np

def frontend(A, Z, C, rx0, rx1):
    x = [np.fromfile(p, dtype=np.complex64) for p in (rx0, rx1)]
    n = min(len(x[0]), len(x[1])); x = [v[A.SKIP:n] for v in x]
    cfo, _ = Z.estimate_cfo(x); ys = [Z.boxcar(Z.derotate(v, Z.F0 + cfo)) for v in x]
    metric = sum(np.abs(Z.pilot_correlation(y, Z.PA)) ** 2 for y in ys)
    peaks, med, top = Z.pick_peaks(metric)
    yks = [(n0, Z.frame_symbols(ys, n0)) for n0 in peaks]; yks = [(n0, k) for n0, k in yks if k is not None]
    om = float(np.median([Z.pilot_om(k) for _, k in yks]))
    hp = [(n0, np.mean(k[:, :C.N_PILOT] * Z.PA, axis=1)) for n0, k in yks]; zacc, npair = 0j, 0
    for (na, ha), (nb, hb) in zip(hp[:-1], hp[1:]):
        if abs((nb - na) - Z.PERIOD) <= 600: zacc += np.sum(np.conj(ha) * hb); npair += 1
    if npair >= 10: om = float(np.angle(zacc) / C.N_SYM)
    if len(yks) > 1:
        pos = np.array([n0 for n0, _ in yks]); keep = []
        for p in pos:
            d = np.abs(pos - p); m = np.rint(d / Z.PERIOD)
            keep.append(bool((((m >= 1) & (m <= 4)) & (np.abs(d - m * Z.PERIOD) <= 600)).any()))
        yks = [t for t, k in zip(yks, keep) if k]
    A.CHAT = A._fit_chat(yks, om)
    return yks, om

def pilot_H(C, Z, yk, om):
    kk = np.arange(C.N_SYM); y = yk * np.exp(-1j * om * kk)[None, :]; pa, pb = C.pilots()
    H = np.stack([np.mean(y[:, :C.N_PILOT] * pa, axis=1), np.mean(y[:, C.N_PILOT:2 * C.N_PILOT] * pb, axis=1)], axis=1)
    noise = np.mean(np.abs(y[:, C.Q1 + 2:]) ** 2, axis=1)
    return y, H, noise

def kalman(Hs, Rs, qmul):
    """Hs: T x 2 x 2 pilot estimates, Rs: T x 2 x 2 measurement variances. Random-walk q per entry from moments."""
    d = np.diff(Hs, axis=0); R = Rs.mean(axis=0)
    q = np.maximum(np.mean(np.abs(d) ** 2, axis=0) - 2 * R, 0.01 * R) * qmul
    X = np.zeros_like(Hs); x = Hs[0].copy(); P = Rs[0].copy(); K = np.zeros((len(Hs), 2, 2))
    for t in range(len(Hs)):
        if t: P = P + q
        k = P / (P + Rs[t]); x = x + k * (Hs[t] - x); P = (1 - k) * P; X[t] = x; K[t] = k
    return X, q, K

def decode(A, Z, C, y, H, noise, det="MMSE"):
    est = Z.detectors(H, A._RMAT(noise), y[:, C.I0:C.Q1])[det]
    return est * np.exp(-0.5j * np.angle(np.sum(est[:, C.N_IDX:] ** 2)))

def qber(A, C, seen, seed=20261030, rseed=777):
    AB, BB = [], []
    for i, e in sorted(seen.items()):
        ab, abit = C.sender_qubits(seed, i); bb = np.random.RandomState([rseed, i]).randint(0, 2, C.N_Q).astype(np.uint8)
        bit = A.measure(e, bb); s = ab == bb; AB.append(abit[s]); BB.append(bit[s])
    ka, kb = np.concatenate(AB), np.concatenate(BB); err = ka != kb
    return float(err.mean()), int(err.sum()), len(ka)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--lib", required=True); ap.add_argument("--tag"); ap.add_argument("--rx0"); ap.add_argument("--rx1")
    ap.add_argument("--dir", default="."); ap.add_argument("--qmul", type=float, nargs="+", default=[1.0]); ap.add_argument("--json"); a = ap.parse_args()
    sys.path.insert(0, str(Path(a.lib).expanduser()))
    import H194E_Z38_COMMON as C, H194E_V18Z37_MIMO_ANALYZE as Z, H194E_V18Z38_QKD_ANALYZE as A
    rx0 = a.rx0 or f"{a.dir}/H194E_V18Z34_{a.tag}_ON_RX0.c64"; rx1 = a.rx1 or f"{a.dir}/H194E_V18Z34_{a.tag}_ON_RX1.c64"
    yks, om = frontend(A, Z, C, rx0, rx1)
    Y, Hs, Ns = zip(*[pilot_H(C, Z, k, om) for _, k in yks]); Hs, Ns = np.array(Hs), np.array(Ns)
    Rs = np.repeat((Ns / C.N_PILOT)[:, :, None], 2, axis=2)                       # var of each pilot estimate = noise_row / N_PILOT
    res = dict(tag=a.tag, frames=len(yks)); out = {}
    for name, HH in [("baseline", Hs)] + [(f"kalman_q{m:g}", None) for m in a.qmul]:
        if HH is None:
            m = float(name.split("_q")[1]); HH, q, K = kalman(Hs, Rs, m)
            res[name + "_gain_mean"] = float(K[len(K) // 2:].mean()); res[name + "_q_over_R"] = float(np.mean(q / Rs.mean(axis=0)))
        seen = {}
        for (n0, _), y, H, nz in zip(yks, Y, HH, Ns):
            e = decode(A, Z, C, y, H, nz); i = A.read_idx(e)
            if i is not None and i not in seen: seen[i] = e
        qb, ne, m = qber(A, C, seen); res[name] = dict(qber=qb, errors=ne, sifted=m, unique=len(seen))
        print(f"{name:14s} QBER {100*qb:.3f}%  errors {ne}/{m}  frames {len(seen)}" + (f"  mean K {res[name+'_gain_mean']:.3f}  q/R {res[name+'_q_over_R']:.3f}" if name != "baseline" else ""))
    if a.json: Path(a.json).write_text(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
