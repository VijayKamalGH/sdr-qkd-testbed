#!/usr/bin/env python3
"""Phase D1 (ISAC, read-only): sensing statistics from an existing capture. Needs the analyzer in the same folder.
 1. Stability of the 2x2 channel estimate H over time: element magnitude (dB) and the relative phases between rows
    (RX0 vs RX1) and between columns (TX streams), which do not depend on a common oscillator phase.
 2. Doppler spectrum of the channel (row-relative phasor) over the longest run of consecutive frames.
 3. Receive-noise (guard-slot) spatial signature: correlation, inter-antenna phase, interferer-to-noise ratio."""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import H194E_V18Z38_QKD_ANALYZE as A
C, Z = A.C, A.Z
T_FRAME = C.N_SYM / (C.FS / C.SPS)                     # 48 ms

def frames_timed(rx0, rx1):
    x = [np.fromfile(p, dtype=np.complex64) for p in (rx0, rx1)]
    n = min(len(x[0]), len(x[1])); x = [v[A.SKIP:n] for v in x]
    cfo, _ = Z.estimate_cfo(x)
    ys = [Z.boxcar(Z.derotate(v, Z.F0 + cfo)) for v in x]
    metric = sum(np.abs(Z.pilot_correlation(y, Z.PA)) ** 2 for y in ys)
    peaks, _, _ = Z.pick_peaks(metric)
    yks = sorted([(n0, Z.frame_symbols(ys, n0)) for n0 in peaks], key=lambda t: t[0]); yks = [(n0, k) for n0, k in yks if k is not None]
    if not yks: sys.exit("No frames found.")
    om = float(np.median([Z.pilot_om(k) for _, k in yks]))
    hp = [(n0, np.mean(k[:, :C.N_PILOT] * Z.PA, axis=1)) for n0, k in yks]
    zacc, npair = 0j, 0
    for (na, ha), (nb, hb) in zip(hp[:-1], hp[1:]):
        if abs((nb - na) - Z.PERIOD) <= 600: zacc += np.sum(np.conj(ha) * hb); npair += 1
    if npair >= 10: om = float(np.angle(zacc) / C.N_SYM)
    out = []
    for n0, yk in yks:
        r = A.decode_frame(yk, om, "MMSE"); H, est = r[0], r[2]
        if A.read_idx(est) is None: continue
        kk = np.arange(C.N_SYM); ykc = yk * np.exp(-1j * om * kk)[None, :]
        out.append((n0 / C.FS, H, ykc[:, C.Q1 + 2:]))
    return out, cfo

def longest_run(t, tol=0.35):
    best = (0, 1); s = 0
    for i in range(1, len(t) + 1):
        if i == len(t) or abs((t[i] - t[i - 1]) - T_FRAME) > tol * T_FRAME:
            if i - s > best[1] - best[0]: best = (s, i)
            s = i
    return best

def doppler(phasor, dt=T_FRAME):
    """phasor: complex series (unit-mean-modulus). Returns freqs (Hz) and power spectrum after removing the mean."""
    v = phasor - np.mean(phasor); w = np.hanning(len(v)); n = max(256, 4 * len(v))
    S = np.abs(np.fft.fftshift(np.fft.fft(v * w, n))) ** 2; f = np.fft.fftshift(np.fft.fftfreq(n, dt)); return f, S

def stats(frames, spacing_m=None):
    t = np.array([f[0] for f in frames]); Hs = np.array([f[1] for f in frames])             # N x 2 x 2
    mag_db = 20 * np.log10(np.abs(Hs)); mag_std = mag_db.std(axis=0)                           # 2x2
    row_rel = np.angle(Hs[:, 0, :] * np.conj(Hs[:, 1, :]))                                     # RX0 vs RX1, per TX column
    col_rel = np.angle(Hs[:, :, 0] * np.conj(Hs[:, :, 1]))                                     # TX0 vs TX1, per RX row
    def cstd(a): return float(np.sqrt(-2 * np.log(np.clip(np.abs(np.mean(np.exp(1j * a), axis=0)), 1e-9, 1))).mean())   # circular std (rad)
    a, b = longest_run(t); run = Hs[a:b]
    dop = None
    if b - a >= 24:
        ph = run[:, 0, 0] * np.conj(run[:, 1, 0]); ph = ph / np.abs(ph).mean()
        f, S = doppler(ph); dc = np.abs(f) <= 0.5; k = np.argmax(S * (~dc))
        dop = dict(frames=int(b - a), peak_hz=float(f[k]), peak_to_floor_db=float(10 * np.log10(S[k] / np.median(S[~dc]))), res_hz=float(1 / ((b - a) * T_FRAME)))
    N = sum(f[2] @ f[2].conj().T for f in frames) / sum(f[2].shape[1] for f in frames)         # guard-slot covariance
    ev = np.linalg.eigvalsh(N); rho = abs(N[0, 1]) / np.sqrt(np.real(N[0, 0] * N[1, 1])); dphi = float(np.angle(N[0, 1]))
    # time variation over windows of 16 frames
    win = []
    for s in range(0, len(frames) - 15, 16):
        Nw = sum(f[2] @ f[2].conj().T for f in frames[s:s + 16]); win.append((abs(Nw[0, 1]) / np.sqrt(np.real(Nw[0, 0] * Nw[1, 1])), np.angle(Nw[0, 1])))
    win = np.array(win) if win else np.zeros((0, 2))
    res = dict(frames=len(frames), mag_std_db=mag_std.round(2).tolist(), row_rel_std_rad=cstd(row_rel), col_rel_std_rad=cstd(col_rel),
               doppler=dop, noise_rho=float(rho), noise_dphi_deg=float(np.degrees(dphi)), inr_db=float(10 * np.log10(max(ev[1] - ev[0], 1e-30) / max(ev[0], 1e-30))),
               rho_win_std=float(win[:, 0].std()) if len(win) > 1 else None,
               dphi_win_std_deg=float(np.degrees(np.sqrt(-2 * np.log(np.clip(abs(np.mean(np.exp(1j * win[:, 1]))), 1e-9, 1))))) if len(win) > 1 else None)
    if spacing_m:
        lam = 3e8 / C.FC; s = dphi * lam / (2 * np.pi * spacing_m); res["doa_deg_uncalibrated"] = float(np.degrees(np.arcsin(s))) if abs(s) <= 1 else None
    return res

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--rx0", type=Path, required=True); ap.add_argument("--rx1", type=Path, required=True)
    ap.add_argument("--tag", default="cap"); ap.add_argument("--spacing-m", type=float, default=None); a = ap.parse_args()
    fr, cfo = frames_timed(a.rx0, a.rx1); r = stats(fr, a.spacing_m); r["tag"] = a.tag
    d = r["doppler"]
    print(f"{a.tag}: frames {r['frames']}  |H| std dB {r['mag_std_db']}  row-rel phase std {r['row_rel_std_rad']:.3f} rad  col-rel {r['col_rel_std_rad']:.3f} rad")
    print(f"   Doppler (longest run {d['frames']} fr, res {d['res_hz']:.2f} Hz): peak {d['peak_hz']:+.2f} Hz, peak-to-floor {d['peak_to_floor_db']:.1f} dB (noise-only reference ~7-9 dB; a moving reflector gives >>12 dB)" if d else "   Doppler: run too short")
    print(f"   noise: |rho| {r['noise_rho']:.3f}  inter-antenna phase {('%+.1f deg' % r['noise_dphi_deg']) if r['noise_rho'] > 0.2 else 'n/a (rho<0.2)'}  INR {r['inr_db']:.1f} dB  window std rho {r['rho_win_std']}  phase {r['dphi_win_std_deg']}")
    Path(f"pd1_{a.tag}.json").write_text(json.dumps(r, indent=1))
