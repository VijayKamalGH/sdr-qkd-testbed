#!/usr/bin/env python3
"""H1.94E V18-Z38 -- Receiver: decode SDR 2x2 MIMO spatial-qubit BB84 from RX0/RX1 captures.
Needs in the same folder: H194E_Z38_COMMON.py, H194E_V18Z37_MIMO_ANALYZE.py (DSP helpers),
H194E_P16B_BB84_CASCADE_UDP.py (Cascade + privacy amplification). numpy + scipy.

Steps: CFO -> matched filter -> frame sync on pilot A -> H from pilots -> MMSE/ZF -> frame index word ->
Receiver measures every qubit in his own random basis (--receiver-seed) -> sifting with Sender's public bases ->
QBER (Z, X, total) -> test subset -> Cascade -> privacy amplification -> key check.
Sender's bases/bits are regenerated from --seed (stands in for the public classical channel + the
test-subset disclosure); the measurement itself never looks at them.
Usage: python3 -I H194E_V18Z38_QKD_ANALYZE.py --rx0 X_RX0.c64 --rx1 X_RX1.c64 --seed 20261030 [--rx1-gain-db 10]"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import H194E_Z38_COMMON as C
import H194E_V18Z37_MIMO_ANALYZE as Z
import H194E_P16B_BB84_CASCADE_UDP as P
SKIP = 200_000

import os
CHAT = None
def _RMAT(noise):
    if CHAT is None: return np.diag(noise)
    sq = np.sqrt(noise); return sq[:, None] * CHAT * sq[None, :]

def _fit_chat(yks, om):
    kk = np.arange(C.N_SYM); Ng = 0
    for _, yk in yks:
        g = (yk * np.exp(-1j * om * kk)[None, :])[:, C.Q1 + 2:]
        Ng = Ng + g @ g.conj().T
    d = np.sqrt(np.real(np.diag(Ng))); Ch = Ng / np.outer(d, d)
    r = abs(Ch[0, 1])
    if r > 0.95: Ch[0, 1] *= 0.95 / r; Ch[1, 0] = np.conj(Ch[0, 1])
    return Ch

def decode_frame(yk, om, det):
    kk = np.arange(C.N_SYM)
    yk = yk * np.exp(-1j * om * kk)[None, :]
    pa, pb = C.pilots()
    H = np.stack([np.mean(yk[:, :C.N_PILOT] * pa, axis=1),
                  np.mean(yk[:, C.N_PILOT:2 * C.N_PILOT] * pb, axis=1)], axis=1)
    noise = np.mean(np.abs(yk[:, C.Q1 + 2:]) ** 2, axis=1)
    dall = yk[:, C.I0:C.Q1]
    est = Z.detectors(H, _RMAT(noise), dall)["MMSE" if det == "ML" else det]   # 2 x (16+272); ML only for qubits
    if os.environ.get("H194E_NOPHASE") != "1":
        est = est * np.exp(-0.5j * np.angle(np.sum(est[:, C.N_IDX:] ** 2)))      # blind common-phase correction
    return H, noise, est, dall

def read_idx(e):
    bits = (e[0, :C.N_IDX].real < 0).astype(np.uint8)
    v = np.packbits(bits[:8])[0]; c = np.packbits(bits[8:])[0]
    return int(v) if (v ^ c) == 255 else None

def measure_ml(d, H, noise, basis):
    """Maximum-likelihood choice between the two states of Receiver's basis, using the measured H and noise."""
    d = d[:, C.N_IDX:]
    S = {(b, v): np.array(C.VEC[(b, v)]) for b in (0, 1) for v in (0, 1)}
    s0 = np.stack([S[(int(b), 0)] for b in basis], axis=1); s1 = np.stack([S[(int(b), 1)] for b in basis], axis=1)
    m0 = np.sum(np.abs(d - H @ s0) ** 2 / noise[:, None], axis=0)
    m1 = np.sum(np.abs(d - H @ s1) ** 2 / noise[:, None], axis=0)
    return (m1 < m0).astype(np.uint8)

def measure(e, basis):
    z1, z2 = e[0, C.N_IDX:].real, e[1, C.N_IDX:].real
    zbit = (np.abs(z2) > np.abs(z1)).astype(np.uint8)
    xbit = (z1 * z2 < 0).astype(np.uint8)
    return np.where(basis == 0, zbit, xbit).astype(np.uint8)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx0", type=Path, required=True); ap.add_argument("--rx1", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=20261030); ap.add_argument("--receiver-seed", type=int, default=777)
    ap.add_argument("--detector", choices=["MMSE", "ZF", "ML"], default="MMSE")
    ap.add_argument("--rx1-gain-db", type=float, default=10.0)
    ap.add_argument("--test", type=float, default=0.1); ap.add_argument("--eps", type=float, default=1e-6)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    x = [np.fromfile(p, dtype=np.complex64) for p in (a.rx0, a.rx1)]
    n = min(len(x[0]), len(x[1])); x = [v[SKIP:n] for v in x]
    print("=" * 76); print("H1.94E V18-Z38 SDR 2x2 MIMO QKD -- RECEIVER"); print("=" * 76)
    cfo, sharp = Z.estimate_cfo(x); print(f"Residual CFO {cfo:+.1f} Hz (line/median {sharp:.0f})")
    ys = [Z.boxcar(Z.derotate(v, Z.F0 + cfo)) for v in x]
    metric = sum(np.abs(Z.pilot_correlation(y, Z.PA)) ** 2 for y in ys)
    peaks, med, top = Z.pick_peaks(metric)
    yks = [(n0, Z.frame_symbols(ys, n0)) for n0 in peaks]; yks = [(n0, k) for n0, k in yks if k is not None]
    if not yks: sys.exit("No frames found (check TX/RX, gains, file names).")
    om = float(np.median([Z.pilot_om(k) for _, k in yks]))      # fallback (noisy at low SNR)
    # Better: residual CFO from the frame-to-frame phase progression of the pilot-A channel estimate
    # (adjacent frames are exactly 480 symbols apart; unambiguous for |residual| < 10 Hz).
    hp = [(n0, np.mean(k[:, :C.N_PILOT] * Z.PA, axis=1)) for n0, k in yks]
    zacc, npair = 0j, 0
    for (na, ha), (nb, hb) in zip(hp[:-1], hp[1:]):
        if abs((nb - na) - Z.PERIOD) <= 600:
            zacc += np.sum(np.conj(ha) * hb); npair += 1
    if npair >= 10:
        om = float(np.angle(zacc) / C.N_SYM)
        print(f"Residual CFO from frame-to-frame pilot phase: {om * C.FS / C.SPS / (2 * np.pi):+.2f} Hz ({npair} frame pairs)")
    if len(yks) > 1:
        pos = np.array([n0 for n0, _ in yks]); keep = []
        for p in pos:
            d = np.abs(pos - p); m = np.rint(d / Z.PERIOD)
            keep.append(bool((((m >= 1) & (m <= 4)) & (np.abs(d - m * Z.PERIOD) <= 600)).any()))
        yks = [t for t, k in zip(yks, keep) if k]
    print(f"Frames synchronised: {len(yks)}   (peak/median {top / max(med, 1e-30):.0f})")
    global CHAT
    if os.environ.get("H194E_DIAGR") == "1": CHAT = None; print("Receive-noise model: DIAGONAL (H194E_DIAGR=1)")
    else:
        CHAT = _fit_chat(yks, om); print(f"Receive-noise model: FULL covariance, pooled |rho| = {abs(CHAT[0, 1]):.3f}")
    print("Blind common-phase correction: " + ("OFF (H194E_NOPHASE=1)" if os.environ.get("H194E_NOPHASE") == "1" else "ON (per frame)"))
    seen, bad_idx, Hs = {}, 0, []
    for n0, yk in yks:
        H, noise, est, dall = decode_frame(yk, om, a.detector)
        i = read_idx(est)
        if i is None: bad_idx += 1; continue
        Hs.append(H)
        if i not in seen: seen[i] = (est, dall, H, noise)
    print(f"Frame index decoded OK: {len(Hs)} frames, {bad_idx} rejected; unique frame indices {len(seen)}")
    sv = np.linalg.svd(np.mean(np.abs(Hs), axis=0), compute_uv=False)
    # Receiver measurement + sifting
    AB, BB, ABAS, BBAS, FR = [], [], [], [], []
    wrong = []
    for i, (e, dall, Hf, nz) in sorted(seen.items()):
        abas, abit = C.sender_qubits(a.seed, i)
        bbas = np.random.RandomState([a.receiver_seed, i]).randint(0, 2, C.N_Q).astype(np.uint8)
        bbit = measure_ml(dall, Hf, nz, bbas) if a.detector == "ML" else measure(e, bbas)
        s = abas == bbas
        AB.append(abit[s]); BB.append(bbit[s]); ABAS.append(abas[s]); FR.append(np.full(s.sum(), i))
        w = ~s; wrong.append(bbit[w])
    ka, kb, bas = np.concatenate(AB), np.concatenate(BB), np.concatenate(ABAS)
    nq = len(seen) * C.N_Q; m = len(ka)
    err = ka != kb
    q = float(err.mean()); qz = float(err[bas == 0].mean()); qx = float(err[bas == 1].mean())
    wb = np.concatenate(wrong); 
    print(f"\nQubits measured {nq} | sifted {m} ({100 * m / nq:.1f}%)")
    print(f"QBER total {100 * q:.2f}%   Z-basis {100 * qz:.2f}%   X-basis {100 * qx:.2f}%   (errors {int(err.sum())})")
    print(f"Wrong-basis outcomes balance (should be ~50% ones): {100 * wb.mean():.1f}%")
    print(f"Channel |H| singular values {sv[0]:.5f}, {sv[1]:.5f} (cond {sv[0] / sv[1]:.2f})")
    # per-stream post-MMSE SINR (unit-power TX stream), averaged over decoded frames -> link-quality metric independent of nominal TX gain
    sinr = []
    for (_e, _d, Hf, nz) in seen.values():
        Ninv = np.linalg.inv(_RMAT(nz))
        Pm = np.linalg.inv(np.eye(2) + Hf.conj().T @ Ninv @ Hf)
        sinr.append([1.0 / Pm[k, k].real - 1.0 for k in range(2)])
    sinr = np.mean(np.array(sinr), axis=0)
    sa, sb_ = 10 * np.log10(max(sinr[0], 1e-12)), 10 * np.log10(max(sinr[1], 1e-12))
    print(f"Post-MMSE SINR per stream: A {sa:+.1f} dB, B {sb_:+.1f} dB (mean {10 * np.log10(max(sinr.mean(), 1e-12)):+.1f} dB)")
    res = dict(qubits=nq, sifted=m, qber=q, qber_z=qz, qber_x=qx, frames=len(seen), cfo_hz=cfo,
               sinr_a_db=float(sa), sinr_b_db=float(sb_), sinr_mean_db=float(10 * np.log10(max(sinr.mean(), 1e-12))),
               sv0=float(sv[0]), sv1=float(sv[1]), cond=float(sv[0] / sv[1]),
               frames_rejected=int(bad_idx), frames_decoded=len(Hs))
    # test subset, Cascade, PA
    rng = np.random.default_rng(5); nt = int(a.test * m); idx = rng.permutation(m); t, k = idx[:nt], idx[nt:]
    qest = float(np.mean(ka[t] != kb[t])); qup = qest + np.sqrt(np.log(1 / a.eps) / (2 * nt))
    print(f"Test subset {nt} bits: Q_est {100 * qest:.2f}%  Q_upper {100 * qup:.2f}% (eps {a.eps:g})")
    if qup > 0.11:
        print("ABORT: Q_upper > 11% -> no secret key (BB84 threshold). Raise TX gain.")
        res.update(abort=True)
    else:
        A, B = ka[k].astype(np.uint8), kb[k].astype(np.uint8)
        # block size from a conservative QBER (a zero-error test sample must not give huge blocks), more passes,
        # then a 64-bit universal-hash confirmation (its 64 bits are counted as leakage)
        Bc, leak = P.cascade(A, B, max(qest, 0.01), np.random.default_rng(9), passes=6)
        ok = bool(np.array_equal(P.toeplitz_pa(A, 64, np.random.default_rng(11)), P.toeplitz_pa(Bc, 64, np.random.default_rng(11))))
        leak += 64
        L = int(max(0, np.floor(len(A) * (1 - P.h(qup)) - leak - 2 * np.log2(1 / a.eps))))
        if not ok:
            print("Reconciliation verification FAILED -> block discarded (no key)"); L = 0
        sa = P.toeplitz_pa(A, L, np.random.default_rng(5)); sb = P.toeplitz_pa(Bc, L, np.random.default_rng(5))
        eq = bool(np.array_equal(sa, sb))
        print(f"Cascade: leaked {leak} parity bits (efficiency f = {(leak / (len(A) * P.h(qest))) if qest > 0 else float('nan'):.2f}) | reconciled: {ok}")
        print(f"Privacy amplification: final key {L} bits | Sender==Receiver: {eq} | key per qubit {L / nq:.4f}")
        res.update(abort=False, leak=leak, reconciled=ok, final_bits=L, keys_equal=eq, key_per_qubit=L / nq)
        if a.out and L: np.packbits(sb).tofile(f"{a.out}_key.bin")
    if a.out: Path(f"{a.out}_qkd.json").write_text(json.dumps(res, indent=2)); print(f"saved {a.out}_qkd.json")

if __name__ == "__main__":
    main()
