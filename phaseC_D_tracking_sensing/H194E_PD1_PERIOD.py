import sys, numpy as np
for tag in sys.argv[1:]:
    x = [np.fromfile(f"H194E_V18Z34_{tag}_ON_RX{r}.c64", dtype=np.complex64, count=3_000_000)[200_000:] for r in (0, 1)]
    e = sum(np.abs(v) ** 2 for v in x); e = np.convolve(e, np.ones(100) / 100, "same"); e = e - e.mean()
    n = len(e); F = np.fft.rfft(e, 2 * n); ac = np.fft.irfft(np.abs(F) ** 2)[:n]; ac /= ac[0]
    lo, hi = 94000, 98000; k = lo + int(np.argmax(ac[lo:hi])); a, b, c = ac[k - 1], ac[k], ac[k + 1]
    frac = 0.5 * (a - c) / (a - 2 * b + c); p = k + frac
    print(f"{tag}: frame period {p:.1f} samples (nominal 96000)  offset {p-96000:+.1f} = {1e6*(p-96000)/96000:+.0f} ppm   autocorr {b:.2f}")
