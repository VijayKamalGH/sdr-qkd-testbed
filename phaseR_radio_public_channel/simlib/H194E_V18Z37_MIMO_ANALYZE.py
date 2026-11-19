#!/usr/bin/env python3
"""
H1.94E  V18-Z37  --  2x2 spatial-multiplexing decoder / analyzer (Receiver side, offline)

Input : RX0 / RX1 recordings (complex64, 2 MS/s) made while H194E_BPSK_TX_V18Z37.py
        sends two independent streams (A on TX1, B on TX2, time-multiplexed pilots).
Does  : CFO estimate (squared-signal line) -> boxcar matched filter -> frame sync on
        pilot A -> per-frame residual-CFO fit -> 2x2 channel matrix H from the pilot A
        and pilot B slots -> detection of both streams with
            MF   (matched filter / no interference cancellation, reference)
            ZF   (zero forcing, H^+ y)
            MMSE (H^H (H H^H + R)^-1 y, R = per-RX noise from the guard)
        -> second-order decision-directed phase tracker per stream -> CRC32 per stream.

Decoding never needs Sender's payloads. The optional --sender-a / --sender-b files are read
only AFTER decoding, solely to count bit errors (BER) over the 288 data bits.

Usage:
  python3 -I H194E_V18Z37_MIMO_ANALYZE.py --rx0 X_RX0.c64 --rx1 X_RX1.c64
        [--rx1-gain-db 10] [--sender-a A.json --sender-b B.json] [--out PREFIX]
Needs numpy only.
"""

import argparse
import json
import sys
import zlib
from pathlib import Path

import numpy as np

FS = 2_000_000
SPS = 200
F0 = 100_000
N_PILOT, N_DATA, N_GUARD = 64, 288, 64
N_SYM = 2 * N_PILOT + N_DATA + N_GUARD   # 480
PERIOD = N_SYM * SPS                     # 96000 samples
SKIP = 200_000                           # ignore first 100 ms (RX start-up transient)
D0, D1 = 2 * N_PILOT, 2 * N_PILOT + N_DATA   # data slot 128..415
DETECTORS = ["MF", "ZF", "MMSE"]


def pilots():
    rs = np.random.RandomState(120396)   # must match H194E_BPSK_TX_V18Z37.py
    pm = lambda b: 1.0 - 2.0 * b.astype(np.float64)
    return pm(rs.randint(0, 2, N_PILOT)), pm(rs.randint(0, 2, N_PILOT))


PA, PB = pilots()


# ------------------------------------------------------------------ signal processing
def estimate_cfo(xs):
    """Residual CFO (Hz) from the squared-signal line (power summed over RX channels).

    For two BPSK streams, s^2 = hA^2 + hB^2 + 2 hA hB sA sB: the constant part is the
    line. It can fade if hA^2 + hB^2 ~ 0 at BOTH receivers; the sync stage reports this.
    """
    n = max(len(x) for x in xs)
    nfft = 1 << (n - 1).bit_length()
    acc = np.zeros(nfft)
    for x in xs:
        acc += np.abs(np.fft.fft(x.astype(np.complex128) ** 2, nfft)) ** 2
    f = np.fft.fftfreq(nfft, 1 / FS)
    win = np.flatnonzero(np.abs(f - 2 * F0) < 60_000)
    k = win[np.argmax(acc[win])]
    a, b, c = np.log(acc[k - 1] + 1e-30), np.log(acc[k] + 1e-30), np.log(acc[k + 1] + 1e-30)
    den = a - 2 * b + c
    frac = 0.5 * (a - c) / den if den != 0 else 0.0
    peak = f[k] + frac * (FS / nfft)
    return peak / 2 - F0, acc[k] / max(np.median(acc[win]), 1e-30)


def derotate(x, f):
    n = np.arange(len(x), dtype=np.float64)
    return (x * np.exp(-2j * np.pi * f * n / FS)).astype(np.complex64)


def boxcar(x):
    """y[n] = sum_{i<200} x[n-i]  (matched filter for rectangular symbols)."""
    c0 = np.concatenate(([0j], np.cumsum(x.astype(np.complex128))))
    y = np.zeros(len(x), np.complex128)
    y[SPS - 1:] = c0[SPS:] - c0[: len(x) - SPS + 1]
    return y


def pilot_correlation(y, pm):
    """c[n] = sum_k pm[k] * y[n + 200 k]."""
    c = np.zeros(len(y), np.complex128)
    for p in range(SPS):
        ys = y[p::SPS]
        if len(ys) < len(pm):
            continue
        cp = np.correlate(ys, pm, mode="valid")
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


def track(u, alpha=0.08, beta=0.004):
    """Second-order decision-directed phase tracker on a complex BPSK stream."""
    th = om = 0.0
    soft = np.empty(len(u))
    for k, uk in enumerate(u):
        v = uk * np.exp(-1j * th)
        soft[k] = v.real
        d = 1.0 if v.real >= 0 else -1.0
        err = d * v.imag / (abs(v) + 1e-12)
        om += beta * err
        th += om + alpha * err
    return soft


def check_crc(bits):
    pay = np.packbits(bits[:256], bitorder="big").tobytes()
    crc_rx = int.from_bytes(np.packbits(bits[256:288], bitorder="big").tobytes(), "big")
    return (zlib.crc32(pay) & 0xFFFFFFFF) == crc_rx, pay


def detectors(H, R, d):
    """d: 2 x N received data (y/200 units). Returns {name: 2 x N complex estimates}."""
    out = {}
    g = np.real(np.sum(np.abs(H) ** 2, axis=0))                    # |h_col|^2
    out["MF"] = (H.conj().T @ d) / g[:, None]
    out["ZF"] = np.linalg.pinv(H) @ d
    W = H.conj().T @ np.linalg.inv(H @ H.conj().T + R)
    z = W @ d
    # unbiased MMSE (scale each stream so its desired-signal gain is 1)
    gain = np.real(np.diag(W @ H))
    out["MMSE"] = z / gain[:, None]
    return out


def frame_symbols(ys, n0):
    idx = n0 + SPS * np.arange(N_SYM)
    if idx[0] < 0 or idx[-1] >= len(ys[0]):
        return None
    return np.array([y[idx] / SPS for y in ys])                    # 2 x 480, per-sample units


def pilot_om(yk):
    """Per-frame residual-CFO estimate (rad/symbol) from pilot A (rough: 64 symbols)."""
    za = yk[:, :N_PILOT] * PA
    return float(np.angle(np.sum(np.conj(za[:, :-1]) * za[:, 1:])))


def decode_frame(yk, om):
    kk = np.arange(N_SYM)
    yk = yk * np.exp(-1j * om * kk)[None, :]
    hA = np.mean(yk[:, :N_PILOT] * PA, axis=1)
    hB = np.mean(yk[:, N_PILOT:2 * N_PILOT] * PB, axis=1)
    H = np.stack([hA, hB], axis=1)                                 # rows RX, cols TX
    # noise: guard slot (pure zeros transmitted), plus pilot residuals as a cross-check
    gd = yk[:, D1 + 2:]
    noise = np.mean(np.abs(gd) ** 2, axis=1)
    R = np.diag(noise)
    d = yk[:, D0:D1]
    res = {"H": H, "om": om, "noise": noise, "det": {}}
    for name, z in detectors(H, R, d).items():
        res["det"][name] = []
        for s in range(2):
            soft = track(z[s])
            bits = (soft < 0).astype(np.uint8)
            ok, pay = check_crc(bits)
            a = np.mean(np.abs(soft))
            err = soft - np.sign(soft) * a
            evm = float(np.sqrt(np.mean(err ** 2)) / max(a, 1e-30))
            res["det"][name].append({"ok": ok, "bits": bits, "payload": pay, "evm": evm, "dup": False})
        a, b = res["det"][name]
        # The two streams carry different payloads. If both pass CRC with identical bytes,
        # one detector is just re-decoding the other stream: do not count stream B twice.
        if a["ok"] and b["ok"] and a["payload"] == b["payload"]:
            b["ok"], b["dup"] = False, True
    return res


def process(x0, x1, verbose=True):
    cfo, sharp = estimate_cfo([x0, x1])
    if verbose:
        print(f"Residual CFO estimate : {cfo:+.1f} Hz  (line/median ratio {sharp:.0f})")
    ys = [boxcar(derotate(x, F0 + cfo)) for x in (x0, x1)]
    metric = sum(np.abs(pilot_correlation(y, PA)) ** 2 for y in ys)
    peaks, med, top = pick_peaks(metric)
    # The capture-wide CFO is already known to well under 1 Hz (squared-signal line), so the
    # leftover per-symbol rotation is the same in every frame. A 64-symbol pilot estimate is
    # far noisier than that at low SNR, so use the MEDIAN over all frames, not each frame's.
    yks = [(n0, frame_symbols(ys, n0)) for n0 in peaks]
    yks = [(n0, yk) for n0, yk in yks if yk is not None]
    om_g = float(np.median([pilot_om(yk) for _, yk in yks])) if yks else 0.0
    frames = []
    for n0, yk in yks:
        r = decode_frame(yk, om_g)
        r["n0"] = n0
        frames.append(r)
    if len(frames) > 1:                       # lattice check: genuine frames repeat every PERIOD
        pos = np.array([f["n0"] for f in frames])
        keep = []
        for p in pos:
            d = np.abs(pos - p)
            m = np.rint(d / PERIOD)
            keep.append(bool((((m >= 1) & (m <= 4)) & (np.abs(d - m * PERIOD) <= 600)).any()))
        frames = [f for f, k in zip(frames, keep) if k]
    if verbose:
        print(f"Frame sync (pilot A)  : {len(frames)} frame(s) (peak/median {top / max(med, 1e-30):.0f})")
    return cfo, frames, len(x0) // PERIOD


# ------------------------------------------------------------------ reporting
def load_bits(path):
    pay = bytes.fromhex(json.loads(Path(path).read_text())["payload_hex"])
    crc = zlib.crc32(pay) & 0xFFFFFFFF
    return np.concatenate([
        np.unpackbits(np.frombuffer(pay, np.uint8), bitorder="big"),
        np.unpackbits(np.frombuffer(crc.to_bytes(4, "big"), np.uint8), bitorder="big")])


def summarize(frames, expected, rx1_gain_db, ref):
    n = len(frames)
    print(f"\nFrames synchronised: {n} of ~{expected} expected")
    if n == 0:
        print("No frames found. Check that TX was running (see carrier line / power level).")
        return
    # H, phase-aligned to H[0,0] of every frame, then averaged
    Hs = np.array([f["H"] for f in frames])
    ref00 = Hs[:, 0, 0] / np.abs(Hs[:, 0, 0])
    Ha = Hs / ref00[:, None, None]
    Hm = Ha.mean(axis=0)
    ph_std = np.abs(np.degrees(np.sqrt(-2 * np.log(np.clip(np.abs(np.mean(np.exp(1j * np.angle(Ha)), axis=0)), 1e-9, 1)))))
    g = np.array([[1.0, 1.0], [10 ** (-rx1_gain_db / 20)] * 2])
    Hn = Hm * g
    print(f"\nChannel matrix H (rows RX0,RX1; cols TX1(A),TX2(B)); RX1 normalised by -{rx1_gain_db:g} dB; "
          "phase relative to H[0,0]")
    for r in range(2):
        print("  " + "   ".join(f"{abs(Hn[r, c]):.5f} ∠{np.degrees(np.angle(Hn[r, c])):+7.1f}° (±{ph_std[r, c]:.1f}°)"
                                for c in range(2)))
    sv = np.linalg.svd(Hn, compute_uv=False)
    print(f"  singular values {sv[0]:.5f}, {sv[1]:.5f}   condition number {sv[0] / sv[1]:.2f} "
          f"({20 * np.log10(sv[0] / sv[1]):.1f} dB)")
    nz = np.array([f["noise"] for f in frames]).mean(axis=0)
    sig = np.mean(np.abs(Hs) ** 2, axis=(0, 2))
    print(f"  per-RX SNR per symbol (signal/noise in boxcar domain): RX0 {10*np.log10(sig[0]/nz[0]):+.1f} dB, "
          f"RX1 {10*np.log10(sig[1]/nz[1]):+.1f} dB")

    print(f"\n{'detector':<9}{'stream':<8}{'CRC ok':>9}{'EVM %':>9}{'post-SNR dB':>13}" +
          ("   BER (data bits)" if ref else ""))
    summary = {}
    for name in DETECTORS:
        for s, lab in enumerate("AB"):
            ok = sum(f["det"][name][s]["ok"] for f in frames)
            dup = sum(f["det"][name][s]["dup"] for f in frames)
            evm = float(np.mean([f["det"][name][s]["evm"] for f in frames]))
            line = f"{name:<9}{lab:<8}{ok:>5}/{n:<3}{100 * evm:>9.1f}{-20 * np.log10(max(evm, 1e-6)):>13.1f}"
            row = {"crc_ok": ok, "frames": n, "evm": evm}
            if dup:
                line += f"  [{dup} frames: duplicate of stream A, not counted]"
                row["duplicates"] = dup
            if ref and ref[s] is not None:
                errs = sum(int(np.sum(f["det"][name][s]["bits"] != ref[s])) for f in frames)
                ber = errs / (288 * n)
                line += f"   {ber:.2e} ({errs} err)"
                row["ber"] = ber
            summary[f"{name}_{lab}"] = row
            print(line)
    print("\nMF = no interference cancellation (reference); ZF/MMSE = spatial separation.")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx0", type=Path, required=True)
    ap.add_argument("--rx1", type=Path, required=True)
    ap.add_argument("--rx1-gain-db", type=float, default=10.0,
                    help="RX1 gain minus RX0 gain (20/30 dB setup -> 10)")
    ap.add_argument("--sender-a", type=Path)
    ap.add_argument("--sender-b", type=Path)
    ap.add_argument("--out", type=str, default=None)
    args = ap.parse_args()

    print("=" * 76)
    print("H1.94E — V18-Z37 2x2 SPATIAL-MULTIPLEXING ANALYZER")
    print("=" * 76)
    x = [np.fromfile(p, dtype=np.complex64) for p in (args.rx0, args.rx1)]
    n = min(len(x[0]), len(x[1]))
    x = [v[SKIP:n] for v in x]
    cfo, frames, expected = process(x[0], x[1])

    ref = None   # payloads are read only now, after decoding is finished
    if args.sender_a or args.sender_b:
        ref = [load_bits(args.sender_a) if args.sender_a else None,
               load_bits(args.sender_b) if args.sender_b else None]
    summary = summarize(frames, expected, args.rx1_gain_db, ref)
    if args.out and summary:
        Path(f"{args.out}_summary.json").write_text(json.dumps({"cfo_hz": cfo, "frames": len(frames),
                                                               "detectors": summary}, indent=2))
        print(f"saved {args.out}_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
