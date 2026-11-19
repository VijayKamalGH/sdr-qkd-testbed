#!/usr/bin/env python3
"""
H1.94E  V18-Z34  --  TX-gain sweep report (Bob side)

Reads capture pairs made by H194E_V18Z34_CAPTURE.py and prints one table row per
capture, using H194E_V18Z34_PRESENCE.py and H194E_V18Z34_ANALYZE.py (same folder):

  tag | RX0/RX1 mean power (dB) | ON-over-OFF level (dB) | presence z | wideband SNR
      | CFO | CRC passes (RX0/RX1/MRC)

If an OFF capture is in the list (same RX gains), "dON/OFF" shows how many dB the
transmission raises the total received power -- an independent check that does not
rely on frame detection.

Usage (pass RX0 files; the matching RX1 file is derived):
  python3 H194E_V18Z34_SWEEP_REPORT.py H194E_V18Z34_G*_RX0.c64
Add --no-decode for a quick presence-only table.
"""

import argparse
import importlib.util
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SKIP = 200_000  # first 100 ms of each capture is ignored (RX start-up transient)


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stem_of(arg):
    s = str(arg)
    return s[: -len("_RX0.c64")] if s.endswith("_RX0.c64") else s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", help="*_RX0.c64 files (or stems)")
    ap.add_argument("--no-decode", action="store_true")
    args = ap.parse_args()

    pres = load("H194E_V18Z34_PRESENCE")
    dec = None if args.no_decode else load("H194E_V18Z34_ANALYZE")

    stems = sorted(set(stem_of(f) for f in args.files))
    rows, off_power = [], None
    for st in stems:
        p0, p1 = Path(f"{st}_RX0.c64"), Path(f"{st}_RX1.c64")
        if not (p0.exists() and p1.exists()):
            print(f"skip {st}: RX0/RX1 file missing")
            continue
        x = [np.fromfile(p, dtype=np.complex64) for p in (p0, p1)]
        n = min(len(x[0]), len(x[1]))
        x = [x[0][SKIP:n], x[1][SKIP:n]]  # ignore RX start-up transient
        pw = [float(np.mean(np.abs(v) ** 2)) for v in x]
        peak = max(float(np.max(np.abs(v))) for v in x)
        is_off = "_OFF" in st
        if is_off and off_power is None:
            off_power = pw
        r = [pres.analyze(v, skip=0) for v in x]
        ld = load("H194E_V18Z34_ANALYZE")
        line_cfo, line_ratio = ld.estimate_cfo(x)
        line_db = 10 * np.log10(max(line_ratio, 1e-30))
        row = {"stem": st, "off": is_off, "pw": pw, "peak": peak, "pres": r,
               "cfo": None, "crc": None, "line_db": line_db, "line_cfo": line_cfo}
        if dec is not None and not is_off:
            try:
                cfo, frames = dec.process(x[0], x[1], verbose=False)
                row["cfo"] = cfo
                row["crc"] = [sum(f["streams"][s]["ok"] for f in frames)
                              for s in dec.STREAMS] + [len(frames)]
            except Exception as exc:  # keep the table going
                row["crc"] = f"error: {exc}"
        rows.append(row)

    print("=" * 110)
    print("H1.94E — V18-Z34 SWEEP REPORT")
    print("=" * 110)
    if off_power is None:
        print("(no OFF capture in the list -> dON/OFF column unavailable)")
    hdr = (f"{'capture':<38}{'P0 dB':>8}{'P1 dB':>8}{'dON/OFF0':>10}{'dON/OFF1':>10}"
           f"{'z0/null':>9}{'z1/null':>9}{'SNR0':>7}{'SNR1':>7}{'line dB':>8}{'line CFO':>9}  CRC rx0/rx1/mrc of N")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        db = [10 * np.log10(p + 1e-30) for p in r["pw"]]
        d = ["   n/a", "   n/a"]
        if off_power is not None and not r["off"]:
            d = [f"{10*np.log10(p / q):+9.2f}" for p, q in zip(r["pw"], off_power)]
        z = [(f"{q['z']:.0f}/{q['z_null_max']:.0f}" + ("*" if q["detected"] else "")) if q else "-"
             for q in r["pres"]]
        snr = [f"{q['snr_db']:+.0f}" if q else "-" for q in r["pres"]]
        cfo = f"{r['line_cfo']:+.0f}"
        c = r["crc"]
        crc = ("-" if c is None else c if isinstance(c, str)
               else f"{c[0]}/{c[1]}/{c[2]} of {c[3]}")
        name = Path(r["stem"]).name + (" [OFF]" if r["off"] else "")
        print(f"{name:<38}{db[0]:>8.1f}{db[1]:>8.1f}{d[0]:>10}{d[1]:>10}"
              f"{z[0]:>9}{z[1]:>9}{snr[0]:>7}{snr[1]:>7}{r['line_db']:>8.1f}{cfo:>9}  {crc}")
        if r["peak"] > 0.9:
            print(f"   ^ WARNING: peak |x| = {r['peak']:.2f}  (possible saturation)")
    print("\nline dB = strength of the BPSK carrier line (x^2 spectrum) over its noise median: "
          "about 12-17 with no TX,\n>20 with the carrier present; 'line CFO' should then repeat "
          "from capture to capture (about -660 Hz so far).")
    print("How to read: z/null = presence z / best wrong-period z; '*' = detected. "
          "dON/OFF should rise ~dB-for-dB with TX gain.\nCRC passes > 0 = decodable. SNR is wideband (2 MHz) and "
          "optimistic when z is low.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
