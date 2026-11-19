#!/usr/bin/env python3
"""H1.94E V18-Z38 -- SDR 2x2 MIMO QKD transmitter (Sender). Spatial-qubit BB84, see H194E_Z38_COMMON.py.
The loop holds --frames distinct frames (default 100 = 4.8 s, 27,200 qubits). Waveforms are written
to .c64 files and played with a repeating file_source (no huge Python lists).
Use the patched gr-osmosdr (PYTHONPATH / LD_LIBRARY_PATH) as for Z37.
  --write-only / --dry-run : generate files / only print, no hardware.
  --eve-rate p             : software intercept-resend Eve acts on a fraction p of qubits (demo, QBER->25%*p)."""
import argparse, time
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import H194E_Z38_COMMON as C

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--frames", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20261030)
    ap.add_argument("--amplitude", type=float, default=0.14)
    ap.add_argument("--gain", type=float, default=30)
    ap.add_argument("--eve-rate", type=float, default=0.0)
    ap.add_argument("--workdir", type=Path, default=Path("."))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write-only", action="store_true")
    a = ap.parse_args()
    if not 1 <= a.frames <= 256: ap.error("--frames must be 1..256")
    eve_rng = np.random.default_rng(a.seed ^ 0xE5E)
    wa, wb = [], []
    for i in range(a.frames):
        sa, sb = C.frame_streams(a.seed, i, a.eve_rate, eve_rng)
        wa.append(C.to_waveform(sa, a.amplitude)); wb.append(C.to_waveform(sb, a.amplitude))
    wa, wb = np.concatenate(wa), np.concatenate(wb)
    print("=" * 70); print("H1.94E V18-Z38 SDR 2x2 MIMO QKD -- SENDER"); print("=" * 70)
    print(f"{a.frames} frames x {C.N_Q} qubits = {a.frames*C.N_Q} qubits per loop ({a.frames*0.048:.2f} s), seed {a.seed}")
    print(f"amplitude {a.amplitude}  TX gain {a.gain} dB  EVE: " + (f"intercept-resend on {100*a.eve_rate:.0f}% of qubits" if a.eve_rate else "DISABLED"))
    if a.dry_run: print("DRY RUN: nothing written"); return
    fa, fb = a.workdir/"H194E_Z38_TX_A.c64", a.workdir/"H194E_Z38_TX_B.c64"
    wa.tofile(fa); wb.tofile(fb); print(f"wrote {fa.name}, {fb.name} ({len(wa)} samples each)")
    if a.write_only: return
    from gnuradio import gr, blocks
    import osmosdr
    tb = gr.top_block()
    sink = osmosdr.sink(args="numchan=2 bladerf=0,nchan=2"); sink.set_sample_rate(C.FS)
    for ch in range(2): sink.set_center_freq(C.FC, ch); sink.set_gain(a.gain, ch)
    tb.connect(blocks.file_source(8, str(fa), True), (sink, 0))
    tb.connect(blocks.file_source(8, str(fb), True), (sink, 1))
    try:
        tb.start(); print("\nV18-Z38 TRANSMISSION ACTIVE", flush=True); time.sleep(a.seconds)
    finally:
        tb.stop(); tb.wait()
    print("V18-Z38 TRANSMISSION COMPLETE")

if __name__ == "__main__":
    main()
