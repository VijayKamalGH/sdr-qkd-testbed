#!/usr/bin/env python3
"""
H1.94E  V18-Z34  --  CFO-independent signal PRESENCE detector (Bob side)

Alice repeats a frame every 96000 samples (48 ms): 352 symbols ON, 128 symbols of
zeros (guard). The received POWER therefore has an ON/OFF pattern with that period,
whatever the CFO or phase. This script folds |x|^2 modulo the frame period, finds the
alignment with the largest ON-minus-OFF contrast, and reports its significance (z)
and the wideband SNR it implies. No CFO estimate, no preamble correlation, so it
works well below the level where decoding is possible.

Reading the result (per channel):
  SIGNAL PRESENT : z at the true period beats z at every wrong period (empirical null)
  NOT DETECTED   : it does not (OFF capture, signal too weak, or noisy receiver)
Real receiver noise fluctuates slowly, so a bare z-score is not a detector; the
wrong-period folds calibrate it. Sensitivity on synthetic data: about -20 dB wideband
SNR. Wideband SNR is defined over the full 2 MHz band, as in the decoder.
The first 100 ms of every capture is ignored (RX start-up transient).
Needs numpy only.

Usage:
  python3 -I H194E_V18Z34_PRESENCE.py --rx0 X_RX0.c64 --rx1 X_RX1.c64
"""

import argparse
from pathlib import Path

import numpy as np

SPS = 200
N_ON, N_OFF = 352, 128
NB = N_ON + N_OFF  # 480 bins of 200 samples = one 96000-sample period
PERIOD = NB * SPS
NULL_PERIODS = [400, 420, 440, 460, 500, 520, 540, 560]  # wrong fold periods (bins)
SKIP = 200_000  # drop the first 100 ms: receiver start-up transient


def scan(x, nb):
    """Best ON-minus-OFF contrast when folding |x|^2 with a period of nb bins."""
    n_on = int(round(nb * N_ON / NB))
    n_off = nb - n_on
    per = nb * SPS
    n_per = len(x) // per
    p = np.abs(x[: n_per * per]).astype(np.float64) ** 2
    pb = p.reshape(n_per, nb, SPS).mean(axis=2)
    m = pb.mean(axis=0)
    var_bin = pb.var(axis=0, ddof=1) / n_per
    best = None
    for s in range(nb):
        on_idx = (s + np.arange(5, n_on - 5)) % nb
        off_idx = (s + n_on + np.arange(5, n_off - 5)) % nb
        on, off = m[on_idx].mean(), m[off_idx].mean()
        se = np.sqrt(var_bin[on_idx].sum() / len(on_idx) ** 2
                     + var_bin[off_idx].sum() / len(off_idx) ** 2)
        z = (on - off) / se
        if best is None or z > best[0]:
            best = (z, s, on, off)
    return best, n_per


def analyze(x, skip=SKIP):
    """z at the true frame period, plus z at WRONG periods (empirical null).

    Real receiver noise has slow power fluctuations that make z large even with no
    signal, so z only counts as a detection if it clearly beats every wrong period.
    """
    x = x[skip:]
    if len(x) // PERIOD < 8:
        return None
    (z, s, on, off), n_per = scan(x, NB)
    nulls = [scan(x, nb)[0][0] for nb in NULL_PERIODS]
    snr = 10 * np.log10(max(on - off, 1e-30) / max(off, 1e-30))
    return {"z": float(z), "z_null_max": float(max(nulls)),
            "z_null_med": float(np.median(nulls)),
            "detected": bool(z > 6 and z > 1.25 * max(nulls)),
            "shift_samples": int(s * SPS), "on_power": float(on),
            "off_power": float(off), "snr_db": float(snr), "periods": int(n_per)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx0", type=Path, required=True)
    ap.add_argument("--rx1", type=Path, required=True)
    args = ap.parse_args()

    print("=" * 72)
    print("H1.94E — V18-Z34 SIGNAL PRESENCE DETECTOR (CFO-independent)")
    print("=" * 72)
    for name, path in (("RX0", args.rx0), ("RX1", args.rx1)):
        x = np.fromfile(path, dtype=np.complex64)
        r = analyze(x)
        if r is None:
            print(f"{name}: capture too short")
            continue
        verdict = ("SIGNAL PRESENT" if r["detected"] else "NOT DETECTED")
        print(f"{name}: z(true period) = {r['z']:.1f}   z(wrong periods): "
              f"median {r['z_null_med']:.1f}, max {r['z_null_max']:.1f}  ->  {verdict}")
        print(f"     ON power  {10*np.log10(r['on_power']+1e-30):.2f} dB   "
              f"OFF(guard) power {10*np.log10(r['off_power']+1e-30):.2f} dB   "
              f"=> wideband SNR {r['snr_db']:+.1f} dB   ({r['periods']} frame periods)"
              + ("" if r["detected"] else "   [SNR figure unreliable: not detected]"))
        print(f"     frame start offset in capture: {r['shift_samples']} samples")
    print("\nDetected only if z at the true 48 ms period exceeds 6 AND 1.25x the best of the "
          "wrong-period folds.")


if __name__ == "__main__":
    main()
