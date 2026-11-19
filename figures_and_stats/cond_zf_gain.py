#!/usr/bin/env python3
"""Per-frame complex condition number, diagonal-to-off-diagonal power and ZF SINR of one capture.

Runs the FROZEN receiver (../lab_capture_and_analysis/H194E_V18Z38_QKD_ANALYZE.py) unchanged and records the channel
estimate H_hat and the receive-noise powers of every frame it accepts (decode_frame is wrapped; nothing is edited).
Usage:  python3 -I cond_zf_gain.py --rx0 X_RX0.c64 --rx1 X_RX1.c64 --seed 20261030 [--rx1-gain-db 10]
Prints quartiles over frames of
   kappa_c  = sigma_max/sigma_min of the complex H_hat   (the analyser's printed index uses |H_ij| and ignores phase)
   dod_dB   = 10 log10((|h11|^2+|h22|^2)/(|h12|^2+|h21|^2))
   ZF SINR  = 1/[H^-1 R H^-H]_kk per stream, R = diag(receive-noise powers), unit stream power
Needs the raw .c64 captures, which are not in this repository. Tested only on a synthetic capture (known H).
"""
import sys, runpy, argparse
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
LAB = HERE.parent / "lab_capture_and_analysis"
sys.path.insert(0, str(LAB))
import H194E_V18Z38_QKD_ANALYZE as A

rec = []
_orig = A.decode_frame
def _wrap(yk, om, det):
    out = _orig(yk, om, det)
    try:
        H, noise = np.asarray(out[0]), np.asarray(out[1]).reshape(-1)
        rec.append((H, noise))
    except Exception:
        pass
    return out
A.decode_frame = _wrap

def summarise():
    k, d, g = [], [], []
    for H, nz in rec:
        sv = np.linalg.svd(H, compute_uv=False); k.append(sv[0] / sv[1])
        a = np.abs(H) ** 2; d.append(10 * np.log10((a[0, 0] + a[1, 1]) / (a[0, 1] + a[1, 0])))
        Hi = np.linalg.inv(H); S = Hi @ np.diag(nz) @ Hi.conj().T
        g.append(np.real(np.diag(S)))                       # 1/SINR_ZF per stream (unit stream power)
    k, d, g = np.array(k), np.array(d), np.array(g)
    q = lambda v: np.percentile(v, [25, 50, 75])
    print(f"frames used: {len(k)}")
    print("complex cond  kappa_c   quartiles %.2f / %.2f / %.2f" % tuple(q(k)))
    print("diag/off-diag power (dB) quartiles %.2f / %.2f / %.2f" % tuple(q(d)))
    for s, n in enumerate("AB"):
        sinr = -10 * np.log10(g[:, s]); print(f"ZF SINR stream {n} (dB)  quartiles %.2f / %.2f / %.2f" % tuple(q(sinr)))
    # relation to singular values for equal noise: noise gain >= 1/sigma_max^2 and <= 1/sigma_min^2 (per unit noise)
    return k, d, g

if __name__ == "__main__":
    A.main()
    summarise()
