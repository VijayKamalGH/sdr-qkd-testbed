#!/usr/bin/env python3
"""Phase D2: per-window motion features from the pilot channel estimates. One CSV line per ~1 s window:
tag,window,frames,dphi_std,dlogH_std,drow_std,dH_rel   (all from consecutive frames only).
Usage: python3 H194E_PD2_MOTION.py --lib <analyser dir> --dir . --tags KQ1 KQ2 ... [--win 21] [--csv out.csv]"""
import argparse, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import H194E_PC_KALMAN as K

def features(Hs, ok, win):
    v = Hs.reshape(len(Hs), 4); rows = []
    for s in range(0, len(v) - win, win):
        idx = [t for t in range(s + 1, s + win + 1) if ok[t - 1]]
        if len(idx) < win // 2: continue
        a, b = v[[t - 1 for t in idx]], v[idx]
        dphi = np.angle(np.sum(b * np.conj(a), axis=1)); dlog = np.log(np.abs(b).sum(1) / np.abs(a).sum(1))
        ra, rb = a[:, 2] / a[:, 0], b[:, 2] / b[:, 0]; drow = np.angle(rb * np.conj(ra))
        dh = np.linalg.norm(b - a, axis=1) / np.linalg.norm(a, axis=1)
        rows.append((len(idx), dphi.std(), dlog.std(), drow.std(), dh.mean()))
    return rows

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--lib", required=True); ap.add_argument("--dir", default=".")
    ap.add_argument("--tags", nargs="+", required=True); ap.add_argument("--win", type=int, default=21); ap.add_argument("--csv"); a = ap.parse_args()
    sys.path.insert(0, str(Path(a.lib).expanduser()))
    import H194E_Z38_COMMON as C, H194E_V18Z37_MIMO_ANALYZE as Z, H194E_V18Z38_QKD_ANALYZE as A
    out = []
    for t in a.tags:
        u = f"{a.dir}/H194E_V18Z34_{t}_ON"; yks, om = K.frontend(A, Z, C, u + "_RX0.c64", u + "_RX1.c64")
        Hs = np.array([K.pilot_H(C, Z, k, om)[1] for _, k in yks]); pos = np.array([n for n, _ in yks])
        ok = np.abs(np.diff(pos) - Z.PERIOD) <= 600
        for w, r in enumerate(features(Hs, ok, a.win)): out.append(f"{t},{w},{r[0]},{r[1]:.4f},{r[2]:.4f},{r[3]:.4f},{r[4]:.4f}")
    print("tag,window,frames,dphi_std,dlogH_std,drow_std,dH_rel"); print("\n".join(out))
    if a.csv: Path(a.csv).write_text("tag,window,frames,dphi_std,dlogH_std,drow_std,dH_rel\n" + "\n".join(out) + "\n")

if __name__ == "__main__":
    main()
