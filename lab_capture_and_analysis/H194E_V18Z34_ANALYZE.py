#!/usr/bin/env python3
"""
H1.94E  V18-Z34  --  offline dual-channel decoder / analyzer (Bob side)

Input : the two .c64 recordings (complex64, 2 MS/s) from H194E_V18Z34_CAPTURE.py
Does  : CFO estimate (squaring) -> boxcar matched filter -> preamble search (both
        channels) -> per-frame phase/slope fit on the preamble -> decision-directed
        phase tracking -> CRC32 check, for RX0 alone, RX1 alone and RX0+RX1 (MRC).

Alice's payload file is NOT needed to decode. The optional --alice-payload is read
only AFTER decoding has finished and the decoded results are printed, and is used
solely to count payload bit errors.

Usage:
  python3 -I H194E_V18Z34_ANALYZE.py --rx0 X_RX0.c64 --rx1 X_RX1.c64 [--out PREFIX]
                                      [--alice-payload H194E_V18Z33P_ALICE_PAYLOAD.json]
"""

import argparse
import csv
import json
import sys
import zlib
from pathlib import Path

import numpy as np

FS = 2_000_000
SPS = 200
F0 = 100_000  # nominal baseband offset

PRE16 = np.array([1, 1, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1, 1, 0, 1, 0], np.uint8)
PRE_BITS = np.tile(PRE16, 4)
N_PRE, N_PAY, N_CRC, N_GUARD = 64, 256, 32, 128
N_FRAME = N_PRE + N_PAY + N_CRC  # 352
PRE_PM = 1.0 - 2.0 * PRE_BITS.astype(np.float64)
PERIOD = (N_FRAME + N_GUARD) * SPS  # 96000 samples (48 ms)
SHIFTS = [0, 16, -16, 32, -32, 48, -48]  # preamble is a 16-bit word x4

STREAMS = ["RX0", "RX1", "MRC"]
SKIP = 200_000  # drop the first 100 ms: receiver start-up transient


# --------------------------------------------------------------------------
# signal processing
# --------------------------------------------------------------------------
def estimate_cfo(xs):
    """Residual CFO (Hz) from the squared-signal tone (BPSK), both channels."""
    n = max(len(x) for x in xs)
    nfft = 1 << (n - 1).bit_length()
    acc = np.zeros(nfft)
    for x in xs:
        acc += np.abs(np.fft.fft(x.astype(np.complex128) ** 2, nfft)) ** 2
    f = np.fft.fftfreq(nfft, 1 / FS)
    win = np.flatnonzero(np.abs(f - 2 * F0) < 60_000)
    k = win[np.argmax(acc[win])]
    # parabolic interpolation on log-power
    a, b, c = np.log(acc[k - 1] + 1e-30), np.log(acc[k] + 1e-30), np.log(acc[k + 1] + 1e-30)
    denom = a - 2 * b + c
    frac = 0.5 * (a - c) / denom if denom != 0 else 0.0
    peak = f[k] + frac * (FS / nfft)
    sharp = acc[k] / max(np.median(acc[win]), 1e-30)
    return peak / 2 - F0, sharp


def derotate(x, f):
    n = np.arange(len(x), dtype=np.float64)
    return (x * np.exp(-2j * np.pi * f * n / FS)).astype(np.complex64)


def boxcar(x):
    """y[n] = sum_{i<200} x[n-i]  (matched filter for rectangular symbols)."""
    c0 = np.concatenate(([0j], np.cumsum(x.astype(np.complex128))))
    y = np.zeros(len(x), np.complex128)
    y[SPS - 1:] = c0[SPS:] - c0[: len(x) - SPS + 1]
    return y


def preamble_correlation(y):
    """c[n] = sum_k pre[k] * y[n + 200k], for every sample offset n."""
    c = np.zeros(len(y), np.complex128)
    for p in range(SPS):
        ys = y[p::SPS]
        if len(ys) < N_PRE:
            continue
        cp = np.correlate(ys, PRE_PM, mode="valid")
        c[p: p + SPS * len(cp): SPS] = cp
    return c


def pick_peaks(metric):
    med = np.median(metric)
    top = metric.max()
    if top < 50 * med:
        return [], med, top
    thr = max(0.2 * top, 50 * med)
    idx = np.flatnonzero(metric > thr)
    idx = idx[np.argsort(-metric[idx])]
    kept = []
    for i in idx:
        if all(abs(i - j) >= PERIOD // 2 for j in kept):
            kept.append(int(i))
    return sorted(kept), med, top


def dd_track(u, alpha=0.08, beta=0.004):
    """Second-order decision-directed phase tracker; preamble = known data."""
    th = om = 0.0
    soft = np.empty(len(u))
    for k, uk in enumerate(u):
        v = uk * np.exp(-1j * th)
        soft[k] = v.real
        d = PRE_PM[k] if k < N_PRE else (1.0 if v.real >= 0 else -1.0)
        err = d * v.imag / (abs(v) + 1e-12)
        om += beta * err
        th += om + alpha * err
    return soft


def check_crc(bits):
    pay = np.packbits(bits[N_PRE: N_PRE + N_PAY], bitorder="big").tobytes()
    crc_rx = int.from_bytes(
        np.packbits(bits[N_PRE + N_PAY:], bitorder="big").tobytes(), "big"
    )
    return (zlib.crc32(pay) & 0xFFFFFFFF) == crc_rx, pay


def decode_frame(ys, n0):
    """ys = [y_rx0, y_rx1] (boxcar outputs); n0 = index of first symbol's end."""
    idx = n0 + SPS * np.arange(N_FRAME)
    if idx[0] < 0 or idx[-1] >= len(ys[0]):
        return None
    kk = np.arange(N_FRAME)
    us, info = [], []
    for y in ys:
        yk = y[idx]
        z = yk[:N_PRE] * PRE_PM
        ph = np.unwrap(np.angle(z))
        om, th = np.polyfit(np.arange(N_PRE), ph, 1)
        mag = float(np.mean(np.abs(z)))
        u = yk * np.exp(-1j * (th + om * kk))
        var = float(np.var((u[:N_PRE] * PRE_PM).imag)) + 1e-30
        us.append(u)
        info.append({"mag": mag, "theta": float(th), "var": var})
    w = [i["mag"] / i["var"] for i in info]
    us.append(w[0] * us[0] + w[1] * us[1])

    res = {"info": info, "streams": {}}
    for name, u in zip(STREAMS, us):
        soft = dd_track(u)
        bits = (soft < 0).astype(np.uint8)
        ok, pay = check_crc(bits)
        res["streams"][name] = {"ok": ok, "payload": pay, "bits": bits}
    return res


def process(x0, x1, verbose=True):
    cfo, sharp = estimate_cfo([x0, x1])
    if verbose:
        print(f"Residual CFO estimate : {cfo:+.1f} Hz  (tone/median ratio {sharp:.0f})")
    d0, d1 = derotate(x0, F0 + cfo), derotate(x1, F0 + cfo)
    ys = [boxcar(d0), boxcar(d1)]
    metric = sum(np.abs(preamble_correlation(y)) ** 2 for y in ys)
    peaks, med, top = pick_peaks(metric)
    if verbose:
        print(f"Preamble search       : {len(peaks)} preamble peak(s) "
              f"(peak/median = {top / max(med, 1e-30):.0f})")

    frames = []
    for n0 in peaks:
        best, best_s = None, 0
        for s in SHIFTS:  # shifts only matter if the CRC fails at s=0
            r = decode_frame(ys, n0 + SPS * s)
            if r is None:
                continue
            if s == 0:
                best, best_s = r, 0
            if r["streams"]["MRC"]["ok"] or any(v["ok"] for v in r["streams"].values()):
                best, best_s = r, s
                break
        if best is None:
            continue
        s0 = n0 + SPS * best_s - (SPS - 1)
        sig = [float(np.mean(np.abs(x[s0: s0 + N_FRAME * SPS]) ** 2))
               if s0 >= 0 and s0 + N_FRAME * SPS <= len(x) else np.nan
               for x in (x0, x1)]
        g0 = s0 + (N_FRAME + 5) * SPS
        g1 = s0 + (N_FRAME + N_GUARD - 5) * SPS
        noi = [float(np.mean(np.abs(x[g0:g1]) ** 2)) if g0 >= 0 and g1 <= len(x) else np.nan
               for x in (x0, x1)]
        best.update(n0=n0 + SPS * best_s, shift_symbols=best_s, sig=sig, noise=noi)
        frames.append(best)

    # Alice repeats frames every PERIOD samples, so genuine detections lie on a
    # lattice (allowing for TX/RX clock offset). Drop detections that fit it with
    # no neighbour: they are spurious correlations, not frames.
    if len(frames) > 1:
        pos = np.array([f["n0"] for f in frames])
        keep = []
        for i, p in enumerate(pos):
            d = np.abs(pos - p)
            m = np.rint(d / PERIOD)
            near = (m >= 1) & (m <= 4) & (np.abs(d - m * PERIOD) <= 600)
            keep.append(bool(near.any()))
        dropped = len(frames) - sum(keep)
        frames = [f for f, k in zip(frames, keep) if k]
        if verbose and dropped:
            print(f"Lattice check         : dropped {dropped} off-grid detection(s)")
    return cfo, frames


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------
def circ_mean_std(angles):
    z = np.mean(np.exp(1j * np.asarray(angles)))
    r = min(abs(z), 1.0)
    return np.degrees(np.angle(z)), np.degrees(np.sqrt(-2 * np.log(max(r, 1e-12))))


def summarize(frames):
    out = {"frames": len(frames), "streams": {}}
    for name in STREAMS:
        ok = sum(f["streams"][name]["ok"] for f in frames)
        out["streams"][name] = {"crc_pass": int(ok),
                                "crc_rate": ok / len(frames) if frames else 0.0}
    for ch in (0, 1):
        sig = np.array([f["sig"][ch] for f in frames])
        noi = np.array([f["noise"][ch] for f in frames])
        # SNR from MEAN powers (a per-frame dB average is wrecked by frames where
        # slow noise fluctuations push the guard power above the frame power)
        ms, mn = float(np.nanmean(sig)) if len(sig) else 1.0, float(np.nanmean(noi)) if len(noi) else 1.0
        snr = np.array([10 * np.log10(max(ms - mn, 1e-30) / max(mn, 1e-30))])
        out[f"rx{ch}"] = {
            "mean_signal_power_dB": float(10 * np.log10(np.nanmean(sig))) if len(sig) else None,
            "mean_noise_power_dB": float(10 * np.log10(np.nanmean(noi))) if len(noi) else None,
            "mean_snr_dB": float(np.nanmean(snr)) if len(snr) else None,
        }
    if frames:
        rel = [f["info"][1]["theta"] - f["info"][0]["theta"] for f in frames]
        m, s = circ_mean_std(rel)
        out["rx1_minus_rx0_phase_deg"] = {"circ_mean": float(m), "circ_std": float(s)}
        ratio = [20 * np.log10(f["info"][1]["mag"] / f["info"][0]["mag"]) for f in frames]
        out["rx1_over_rx0_dB"] = {"mean": float(np.mean(ratio)), "std": float(np.std(ratio))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx0", type=Path, required=True)
    ap.add_argument("--rx1", type=Path, required=True)
    ap.add_argument("--out", type=str, default=None, help="prefix for CSV/JSON output")
    ap.add_argument("--alice-payload", type=Path, default=None,
                    help="optional; read only after decoding, for bit-error counting")
    args = ap.parse_args()

    print("=" * 72)
    print("H1.94E — V18-Z34 OFFLINE DECODER (Bob side)")
    print("=" * 72)
    x0 = np.fromfile(args.rx0, dtype=np.complex64)
    x1 = np.fromfile(args.rx1, dtype=np.complex64)
    if len(x0) != len(x1):
        n = min(len(x0), len(x1))
        print(f"WARNING: length mismatch, truncating to {n} samples")
        x0, x1 = x0[:n], x1[:n]
    x0, x1 = x0[SKIP:], x1[SKIP:]  # ignore RX start-up transient (first 100 ms)
    print(f"Samples per channel   : {len(x0):,}  ({len(x0) / FS:.2f} s)")

    cfo, frames = process(x0, x1)
    if not frames:
        print("\nNo frames detected (expected for an OFF/noise-floor capture).")
        print(f"RX0 power: {10*np.log10(np.mean(np.abs(x0)**2)+1e-30):.1f} dB   "
              f"RX1 power: {10*np.log10(np.mean(np.abs(x1)**2)+1e-30):.1f} dB")
        return 0

    summ = summarize(frames)
    print("\n--- decode results (before any comparison with Alice) ---")
    for name in STREAMS:
        s = summ["streams"][name]
        print(f"{name:>4}: CRC pass {s['crc_pass']:>3}/{summ['frames']:<3} "
              f"({100 * s['crc_rate']:.1f} %)")
    for ch in (0, 1):
        r = summ[f"rx{ch}"]
        print(f"RX{ch}: signal {r['mean_signal_power_dB']:.1f} dB, "
              f"noise(guard) {r['mean_noise_power_dB']:.1f} dB, SNR {r['mean_snr_dB']:.1f} dB")
    p, r = summ["rx1_minus_rx0_phase_deg"], summ["rx1_over_rx0_dB"]
    print(f"RX1-RX0 phase: mean {p['circ_mean']:+.1f} deg, circ-std {p['circ_std']:.1f} deg")
    print(f"RX1/RX0 level: mean {r['mean']:+.1f} dB, std {r['std']:.1f} dB")

    # distinct CRC-valid payloads
    for name in STREAMS:
        pays = {}
        for f in frames:
            st = f["streams"][name]
            if st["ok"]:
                pays[st["payload"].hex()] = pays.get(st["payload"].hex(), 0) + 1
        for h, c in pays.items():
            print(f"{name:>4} CRC-valid payload x{c}: {h}")

    # optional comparison, only now
    if args.alice_payload is not None:
        exp = bytes.fromhex(json.load(args.alice_payload.open())["payload_hex"])
        exp_bits = np.unpackbits(np.frombuffer(exp, np.uint8), bitorder="big")
        print("\n--- comparison with Alice's payload (after decoding) ---")
        for name in STREAMS:
            errs = sum(int(np.sum(f["streams"][name]["bits"][N_PRE:N_PRE + N_PAY] != exp_bits))
                       for f in frames)
            tot = N_PAY * len(frames)
            print(f"{name:>4}: payload bit errors {errs}/{tot}  (BER {errs / tot:.2e})")
            summ["streams"][name]["payload_ber"] = errs / tot

    if args.out:
        Path(f"{args.out}_summary.json").write_text(json.dumps({"cfo_hz": cfo, **summ}, indent=2))
        with open(f"{args.out}_frames.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["frame", "n0", "shift_sym", "crc_rx0", "crc_rx1", "crc_mrc",
                        "mag_rx0", "mag_rx1", "theta_rx0", "theta_rx1",
                        "sig_rx0", "sig_rx1", "noise_rx0", "noise_rx1"])
            for i, f in enumerate(frames):
                w.writerow([i, f["n0"], f["shift_symbols"],
                            *(int(f["streams"][n]["ok"]) for n in STREAMS),
                            f["info"][0]["mag"], f["info"][1]["mag"],
                            f["info"][0]["theta"], f["info"][1]["theta"],
                            *f["sig"], *f["noise"]])
        print(f"\nSaved {args.out}_summary.json and {args.out}_frames.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
