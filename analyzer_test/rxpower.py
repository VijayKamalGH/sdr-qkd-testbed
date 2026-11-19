#!/usr/bin/env python3
"""Relative received power of a two-channel capture (.c64, complex64, 2 MS/s).
Usage: python3 rxpower.py RX0.c64 [RX1.c64 ...]
Reports per file: total RMS and peak (1.0 = ADC full scale), total level in dBFS, in-band signal level (the BPSK signal sits at +100 kHz),
noise floor level (estimated away from the signal) and the in-band SNR.  All values are RELATIVE to full scale: dBFS, not dBm. Accuracy about +-3 dB (use it to compare captures, not as a calibrated power)."""
import sys, numpy as np
FS, F0, HALF = 2_000_000, 100_000, 30_000       # sample rate, signal offset, half width of the signal band (Hz)
N = 1 << 22                                      # about 2.1 s of samples

def analyse(path):
    x = np.memmap(path, dtype=np.complex64, mode="r")
    x = np.array(x[min(len(x) // 4, 1_000_000):][:N])          # skip the start-up transient
    rms, peak = float(np.sqrt(np.mean(np.abs(x) ** 2))), float(np.max(np.abs(x)))
    seg = 8192
    w = np.hanning(seg); k = len(x) // seg
    P = np.mean([np.abs(np.fft.fftshift(np.fft.fft(x[i * seg:(i + 1) * seg] * w))) ** 2 for i in range(k)], axis=0) / (np.sum(w ** 2) * seg)
    f = np.fft.fftshift(np.fft.fftfreq(seg, 1 / FS)); df = f[1] - f[0]
    sig = (np.abs(f - F0) <= HALF)
    noise = ((np.abs(f) > 250_000) & (np.abs(f) < 450_000))     # far from the signal, inside the 1 MHz filter
    p_sig_total = P[sig].sum()                                   # power in the signal band (signal + noise there)
    n_density = np.median(P[noise]) / np.log(2)                  # noise power per bin (the median of noise power is ln2 of its mean)
    p_noise_in_sig = n_density * sig.sum()
    p_sig = max(p_sig_total - p_noise_in_sig, 1e-30)
    db = lambda v: 10 * np.log10(v)
    print(f"{path}")
    print(f"  total   : RMS {rms:.5f} ({20*np.log10(rms):6.1f} dBFS), peak |x| {peak:.3f}" + ("   <-- WARNING: near ADC saturation" if peak > 0.9 else ""))
    print(f"  signal  : {db(p_sig):6.1f} dBFS  (band {F0/1e3-HALF/1e3:.0f}..{F0/1e3+HALF/1e3:.0f} kHz)")
    print(f"  noise   : {db(p_noise_in_sig):6.1f} dBFS  (same bandwidth, floor measured at 250..450 kHz)")
    print(f"  in-band SNR: {db(p_sig) - db(p_noise_in_sig):5.1f} dB   (both streams and both TX antennas together; not the pilot-based SINR of the analyser)")

for p in sys.argv[1:]:
    analyse(p)
