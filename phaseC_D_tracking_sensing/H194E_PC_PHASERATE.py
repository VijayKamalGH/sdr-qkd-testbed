#!/usr/bin/env python3
"""Phase C2: track the residual carrier rate of the channel phase and remove the within-frame phase ramp.
Per frame, the Sender-to-Receiver phase advance m_k = angle(<H_k, H_{k-1}>) (480 symbols apart) measures the residual rate.
A causal scalar Kalman filter smooths it (random-walk rate); the data are then de-rotated by exp(-j w (k - kc)) and the
columns of H are shifted to the common reference kc (pilot A centred at 31.5, pilot B at 95.5, kc = 63.5).
Usage: python3 H194E_PC_PHASERATE.py --lib <analyser dir> --dir . --tag KQ4 [--qr 0.01 0.1 1]"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import H194E_PC_KALMAN as K

def rate_filter(m, qr):
    """m: per-frame phase advance (rad per frame, NaN where previous frame missing). Returns w_k (rad/symbol), causal."""
    z = np.where(np.isnan(m), 0, m); good = ~np.isnan(m)
    R = max(np.nanvar(np.diff(m[good])) / 2.0, 1e-6); q = qr * R
    x, P, out = z[good][0] if good.any() else 0.0, R, np.zeros(len(m))
    for t in range(len(m)):
        P += q
        if good[t]:
            k = P / (P + R); x += k * (z[t] - x); P *= 1 - k
        out[t] = x / 480.0
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--lib", required=True); ap.add_argument("--tag"); ap.add_argument("--dir", default=".")
    ap.add_argument("--qr", type=float, nargs="+", default=[0.01, 0.1, 1.0]); ap.add_argument("--json"); a = ap.parse_args()
    sys.path.insert(0, str(Path(a.lib).expanduser()))
    import H194E_Z38_COMMON as C, H194E_V18Z37_MIMO_ANALYZE as Z, H194E_V18Z38_QKD_ANALYZE as A
    u = f"{a.dir}/H194E_V18Z34_{a.tag}_ON"; yks, om = K.frontend(A, Z, C, u + "_RX0.c64", u + "_RX1.c64")
    Y, Hs, Ns = zip(*[K.pilot_H(C, Z, k, om) for _, k in yks]); Hs = np.array(Hs); Ns = np.array(Ns)
    pos = np.array([n for n, _ in yks]); m = np.full(len(Hs), np.nan)
    for t in range(1, len(Hs)):
        if abs((pos[t] - pos[t - 1]) - Z.PERIOD) <= 600: m[t] = np.angle(np.sum(Hs[t] * np.conj(Hs[t - 1])))
    kc = 63.5; kk = np.arange(C.N_SYM); res = dict(tag=a.tag)
    for name, w in [("baseline", np.zeros(len(Hs)))] + [(f"rate_qr{q:g}", rate_filter(m, q)) for q in a.qr]:
        seen = {}
        for t, y in enumerate(Y):
            y2 = y * np.exp(-1j * w[t] * (kk - kc))[None, :]
            H2 = Hs[t] * np.exp(1j * w[t] * np.array([kc - 31.5, kc - 95.5]))[None, :]
            e = K.decode(A, Z, C, y2, H2, Ns[t]); i = A.read_idx(e)
            if i is not None and i not in seen: seen[i] = e
        qb, ne, ms = K.qber(A, C, seen); res[name] = dict(qber=qb, errors=ne, sifted=ms, frames=len(seen))
        print(f"{name:14s} QBER {100*qb:.3f}%  errors {ne}/{ms}  frames {len(seen)}  rms rate {np.sqrt(np.mean(w**2))*480/(2*np.pi)/0.048:.2f} Hz")
    if a.json: Path(a.json).write_text(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
