#!/usr/bin/env python3
"""
H1.94E  V18-Z34  --  independent dual-channel RF capture (Bob side)

Same procedure as V18-Z33P_CAPTURE: runs the existing
H194E_BB84_RF_DUAL_CAPTURE_V4.py (RX0 + RX1, 915 MHz, 2 MS/s, 2 s),
checks the file sizes, then renames the raw recordings to NEW filenames:

    H194E_V18Z34_[<TAG>_]<STATE>_RX0.c64
    H194E_V18Z34_[<TAG>_]<STATE>_RX1.c64

STATE is ON (Alice transmitting) or OFF (Alice silent, noise floor).
TAG is optional, e.g. BOTH_P000, BOTH_P090, TX0ONLY, TX1ONLY.

Existing recordings are never overwritten. A small .meta.json is written next to
each pair, with RMS/peak levels as a saturation check.
The decoder never needs Alice's payload file.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

FS = 2_000_000
BYTES_PER_SAMPLE = 8  # complex64

parser = argparse.ArgumentParser()
parser.add_argument("--state", choices=["ON", "OFF"], required=True)
parser.add_argument("--tag", default="", help="optional label, e.g. BOTH_P090")
parser.add_argument("--seconds", type=int, default=2)
args = parser.parse_args()

if args.seconds <= 0:
    parser.error("--seconds must be positive")
if args.tag and not re.fullmatch(r"[A-Za-z0-9_\-]+", args.tag):
    parser.error("--tag may contain only letters, digits, _ and -")

state = args.state
stem = "H194E_V18Z34_" + (f"{args.tag}_" if args.tag else "") + state
expected_bytes = FS * args.seconds * BYTES_PER_SAMPLE

print("=" * 72)
print("H1.94E — V18-Z34 INDEPENDENT RF CAPTURE")
print("=" * 72)
print(f"Measurement state : {state}")
print(f"Tag               : {args.tag or '-'}")
print("Receiver          : bladeRF RX0 + RX1")
print("RF frequency      : 915 MHz")
print("Sample rate       : 2 MS/s")
print(f"Capture duration  : {args.seconds} seconds")

outputs = [Path(f"{stem}_RX0.c64"), Path(f"{stem}_RX1.c64")]
meta_path = Path(f"{stem}.meta.json")

raw_files = [
    Path("H194E_BB84_RF_RX0_V4.c64"),
    Path("H194E_BB84_RF_RX1_V4.c64"),
]

# Protect completed recordings.
for path in outputs + [meta_path]:
    if path.exists():
        raise SystemExit(
            f"ERROR: {path} already exists. "
            "Existing recording will not be overwritten."
        )

# Protect unrelated or unfinished temporary recordings.
for path in raw_files:
    if path.exists():
        raise SystemExit(
            f"ERROR: Temporary file {path} already exists. "
            "Move or archive it before starting this capture."
        )

print("\nStarting dual-channel capture...", flush=True)

import subprocess  # noqa: E402

subprocess.run(
    [
        "python3",
        "-u",
        "H194E_BB84_RF_DUAL_CAPTURE_V4.py",
        "--seconds",
        str(args.seconds),
    ],
    check=True,
)

for path in raw_files:
    if not path.exists():
        raise SystemExit(f"ERROR: Missing recording {path}")
    size = path.stat().st_size
    if size != expected_bytes:
        raise SystemExit(
            f"ERROR: Invalid recording size: {path}: {size:,} bytes "
            f"(expected {expected_bytes:,})"
        )

# Level check before renaming (read-only).
levels = {}
for ch, path in enumerate(raw_files):
    x = np.fromfile(path, dtype=np.complex64)
    rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
    peak = float(np.max(np.abs(x)))
    levels[f"RX{ch}"] = {"rms": rms, "peak": peak}
    print(f"RX{ch}: RMS={rms:.5f}  peak|x|={peak:.4f}")
    if peak > 0.9:
        print(f"WARNING: RX{ch} peak > 0.9 -- possible ADC saturation; "
              "lower RX gain or TX amplitude/gain.")

for source, destination in zip(raw_files, outputs):
    source.rename(destination)
    print(f"SAVED: {destination} ({destination.stat().st_size:,} bytes)")

meta = {
    "script": "H194E_V18Z34_CAPTURE.py",
    "utc_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "state": state,
    "tag": args.tag,
    "seconds": args.seconds,
    "sample_rate": FS,
    "levels": levels,
    "files": [str(p) for p in outputs],
}
meta_path.write_text(json.dumps(meta, indent=2))
print(f"SAVED: {meta_path}")

print("\nV18-Z34 DUAL-CHANNEL CAPTURE: PASS")
