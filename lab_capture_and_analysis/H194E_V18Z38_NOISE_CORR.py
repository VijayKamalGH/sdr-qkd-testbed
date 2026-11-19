#!/usr/bin/env python3
"""Noise-origin test: how correlated is the receive noise between RX0 and RX1 (sender OFF captures)?
Usage: python3 H194E_V18Z38_NOISE_CORR.py H194E_V18Z34_N01_OFF_RX0.c64 H194E_V18Z34_N01_OFF_RX1.c64"""
import sys, numpy as np
x0 = np.fromfile(sys.argv[1], dtype=np.complex64)[200000:]; x1 = np.fromfile(sys.argv[2], dtype=np.complex64)[200000:]
n = min(len(x0), len(x1)); x0 = x0[:n].astype(np.complex128); x1 = x1[:n].astype(np.complex128)
def rho(a, b): return np.vdot(a, b) / np.sqrt(np.vdot(a, a).real * np.vdot(b, b).real)
print(f"samples {n}   rms RX0 {np.sqrt(np.mean(abs(x0)**2)):.5f}  RX1 {np.sqrt(np.mean(abs(x1)**2)):.5f}   DC RX0 {abs(x0.mean()):.2e} RX1 {abs(x1.mean()):.2e}")
r = rho(x0 - x0.mean(), x1 - x1.mean()); print(f"Broadband correlation (raw samples, DC removed): |rho| = {abs(r):.3f}")
# symbol-rate view, same as the guard slots in the analyzer: boxcar 200 samples
m = n // 200 * 200; b0 = x0[:m].reshape(-1, 200).mean(1); b1 = x1[:m].reshape(-1, 200).mean(1)
print(f"After 200-sample boxcar (10 ksym/s):  |rho| = {abs(rho(b0, b1)):.3f}")
# coherence vs frequency (Welch, 4096-pt)
L = 4096; K = n // L; w = np.hanning(L)
X0 = np.fft.fft(x0[:K*L].reshape(K, L) * w, axis=1); X1 = np.fft.fft(x1[:K*L].reshape(K, L) * w, axis=1)
S00 = (abs(X0)**2).mean(0); S11 = (abs(X1)**2).mean(0); S01 = (X0.conj() * X1).mean(0); coh = abs(S01)**2 / (S00 * S11)
f = np.fft.fftfreq(L, 1 / 2e6); o = np.argsort(f); f, coh, S00, S11 = f[o], coh[o], S00[o], S11[o]
print("Coherence (0 = independent, 1 = identical) by band, and the 5 most coherent frequency bins:")
for lo, hi in ((-1e6, -5e5), (-5e5, -1e5), (-1e5, -5e3), (-5e3, 5e3), (5e3, 1e5), (1e5, 5e5), (5e5, 1e6)):
    mk = (f >= lo) & (f < hi); print(f"  {lo/1e3:7.0f} .. {hi/1e3:6.0f} kHz   mean coherence {coh[mk].mean():.3f}")
for i in np.argsort(coh)[-5:][::-1]: print(f"  bin {f[i]/1e3:9.2f} kHz  coherence {coh[i]:.2f}")
print("Spectral flatness (peak / median power, RX0 | RX1):", f"{S00.max()/np.median(S00):.1f} | {S11.max()/np.median(S11):.1f}", "(about 5 or less = flat noise; large = spurs)")
