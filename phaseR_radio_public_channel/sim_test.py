"""Loopback test of the radio pipe with a synthetic 2x2 channel: python3 sim_test.py LIB ANALYSERDIR [snr_db] [nbytes]"""
import sys, os, numpy as np, subprocess
from pathlib import Path
lib, adir = sys.argv[1], sys.argv[2]; snr = float(sys.argv[3]) if len(sys.argv) > 3 else 25; nb = int(sys.argv[4]) if len(sys.argv) > 4 else 600
sys.path[:0] = [lib, adir, str(Path(__file__).parent)]
import H194E_Z38_COMMON as C, H194E_R1_RADIO_PIPE as R
rng = np.random.default_rng(5); msg = bytes(rng.integers(0, 256, nb, dtype=np.uint8))
fr = R.build_frames(msg, 7); wa, wb = R.waveforms(C, fr, 0.14); L = len(wa)
N = 3 * L + 400_000; off = int(rng.integers(0, 96000))
base = lambda w: np.tile(w, 5)[off:off + N]
H = np.array([[0.9 * np.exp(0.3j), 0.35 * np.exp(-1.2j)], [0.2 * np.exp(2.1j), 0.6 * np.exp(0.7j)]]); cfo = -548.0
lo = np.exp(1j * rng.uniform(0, 6.28)); t = np.arange(N)
for i in range(2):
    s = (H[i, 0] * base(wa) + H[i, 1] * base(wb)) * np.exp(2j * np.pi * cfo * t / 2e6) * lo
    nv = np.mean(np.abs(s) ** 2) / 10 ** (snr / 10)
    s = s + np.sqrt(nv / 2) * (rng.standard_normal(N) + 1j * rng.standard_normal(N)); s.astype(np.complex64).tofile(f"/tmp/r1sim_RX{i}.c64")
import H194E_V18Z37_MIMO_ANALYZE as Z, H194E_V18Z38_QKD_ANALYZE as A
copies, nfr, c = R.decode_capture(A, Z, C, "/tmp/r1sim_RX0.c64", "/tmp/r1sim_RX1.c64")
got, info = R.assemble(copies, 7); print(info, "frames sync", nfr, "cfo", round(float(c), 1)); print("MATCH" if got == msg else "FAIL")
