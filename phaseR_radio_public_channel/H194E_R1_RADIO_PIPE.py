#!/usr/bin/env python3
"""H1.94E R1 -- radio pipe: send an arbitrary message over the SDR 2x2 MIMO link (either direction).
Each radio frame (48 ms) carries 34 bytes = 30 data bytes + CRC32, written with the same spatial-qubit frame as the
BB84 tests but in the Z basis only (bit 0 -> TX1, bit 1 -> TX2), so the same pilots, synchronisation and MMSE front end are used.
The frame index word (0..255) numbers the chunks; the transmitter repeats the whole message in a loop, the receiver keeps the
first copy of every chunk whose CRC is valid. One message holds at most 256 chunks (7,672 bytes).
  tx : python3 H194E_R1_RADIO_PIPE.py tx --lib DIR --file msg.bin --msgid 1 --gain 34 --seconds 300
  rx : python3 H194E_R1_RADIO_PIPE.py rx --lib DIR --rx0 X_RX0.c64 --rx1 X_RX1.c64 --msgid 1 --out got.bin
--lib = folder with H194E_Z38_COMMON.py (tx) and, for rx, also the Z37/Z38 analyser files. Classical symbols only."""
import argparse, os, struct, sys, time, zlib
from pathlib import Path
import numpy as np

DATA = 30                                        # data bytes per radio frame (+4 bytes CRC32 = 34 bytes = 272 bits)
MAXF = 256

def build_frames(msg: bytes, msgid: int):
    body = b"R1" + struct.pack("!HI", msgid & 0xFFFF, len(msg)) + msg
    body += bytes((-len(body)) % DATA)
    n = len(body) // DATA
    if n > MAXF: raise ValueError(f"message too long: {n} chunks > {MAXF} (max {MAXF*DATA-8} bytes)")
    out = []
    for i in range(n):
        d = body[i * DATA:(i + 1) * DATA]
        out.append(d + struct.pack("!I", zlib.crc32(bytes([msgid & 255, i]) + d)))
    return out

def frame_ok(raw: bytes, idx: int, msgid: int):
    return len(raw) == DATA + 4 and zlib.crc32(bytes([msgid & 255, idx]) + raw[:DATA]) == struct.unpack("!I", raw[DATA:])[0]

def payload_streams(C, idx, frame34):
    bits = np.unpackbits(np.frombuffer(frame34, np.uint8))
    pa, pb = C.pilots(); sa, sb = np.zeros(C.N_SYM), np.zeros(C.N_SYM)
    sa[:C.N_PILOT], sb[C.N_PILOT:2 * C.N_PILOT] = pa, pb
    sa[C.I0:C.Q0] = C.idx_symbols(idx)
    sa[C.Q0:C.Q1] = (bits == 0); sb[C.Q0:C.Q1] = (bits == 1)       # Z basis: |0> on TX1, |1> on TX2
    return sa, sb

def waveforms(C, frames, amplitude):
    wa, wb = [], []
    for i, f in enumerate(frames):
        sa, sb = payload_streams(C, i, f); wa.append(C.to_waveform(sa, amplitude)); wb.append(C.to_waveform(sb, amplitude))
    return np.concatenate(wa), np.concatenate(wb)

def assemble(copies, msgid):
    """copies: {idx: [raw34, ...]} -> (message or None, info). Needs frame 0 for the length."""
    good = {}
    for i, lst in copies.items():
        for raw in lst:
            if frame_ok(raw, i, msgid): good[i] = raw[:DATA]; break
    info = dict(idx_seen=len(copies), idx_valid=len(good))
    if 0 not in good or good[0][:2] != b"R1": info["error"] = "frame 0 missing"; return None, info
    mid, ln = struct.unpack("!HI", good[0][2:8]); n = -(-(8 + ln) // DATA)
    info.update(msgid_in_frame=mid, length=ln, chunks=n)
    miss = [i for i in range(n) if i not in good]
    if miss: info["missing"] = miss[:20]; info["n_missing"] = len(miss); return None, info
    return b"".join(good[i] for i in range(n))[8:8 + ln], info

def decode_capture(A, Z, C, rx0, rx1):
    """Analyser front end (as in the B2 receiver) -> {frame idx: [34-byte copies]}, number of frames synchronised."""
    x = [np.fromfile(p, dtype=np.complex64) for p in (rx0, rx1)]
    n = min(len(x[0]), len(x[1])); x = [v[A.SKIP:n] for v in x]
    cfo, _ = Z.estimate_cfo(x); ys = [Z.boxcar(Z.derotate(v, Z.F0 + cfo)) for v in x]
    metric = sum(np.abs(Z.pilot_correlation(y, Z.PA)) ** 2 for y in ys)
    peaks, med, top = Z.pick_peaks(metric)
    yks = [(n0, Z.frame_symbols(ys, n0)) for n0 in peaks]; yks = [(n0, k) for n0, k in yks if k is not None]
    if not yks: return {}, 0, cfo
    om = float(np.median([Z.pilot_om(k) for _, k in yks]))
    hp = [(n0, np.mean(k[:, :C.N_PILOT] * Z.PA, axis=1)) for n0, k in yks]; zacc, npair = 0j, 0
    for (na, ha), (nb, hb) in zip(hp[:-1], hp[1:]):
        if abs((nb - na) - Z.PERIOD) <= 600: zacc += np.sum(np.conj(ha) * hb); npair += 1
    if npair >= 10: om = float(np.angle(zacc) / C.N_SYM)
    if len(yks) > 1:
        pos = np.array([n0 for n0, _ in yks]); keep = []
        for p in pos:
            d = np.abs(pos - p); m = np.rint(d / Z.PERIOD)
            keep.append(bool((((m >= 1) & (m <= 4)) & (np.abs(d - m * Z.PERIOD) <= 600)).any()))
        yks = [t for t, k in zip(yks, keep) if k]
    if hasattr(A, "_fit_chat"): A.CHAT = A._fit_chat(yks, om)
    out, zero = {}, np.zeros(C.N_Q, np.uint8)
    for n0, yk in yks:
        est = A.decode_frame(yk, om, "MMSE")[2]; i = A.read_idx(est)
        if i is None: continue
        out.setdefault(i, []).append(np.packbits(A.measure(est, zero)).tobytes())
    return out, len(yks), cfo

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["tx", "rx"]); ap.add_argument("--lib", required=True)
    ap.add_argument("--file"); ap.add_argument("--msgid", type=int, default=1); ap.add_argument("--gain", type=float, default=34)
    ap.add_argument("--amplitude", type=float, default=0.14); ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--workdir", default="."); ap.add_argument("--write-only", action="store_true")
    ap.add_argument("--rx0"); ap.add_argument("--rx1"); ap.add_argument("--out"); a = ap.parse_args()
    sys.path.insert(0, str(Path(a.lib).expanduser())); import H194E_Z38_COMMON as C
    if a.mode == "tx":
        msg = Path(a.file).read_bytes(); fr = build_frames(msg, a.msgid); wa, wb = waveforms(C, fr, a.amplitude)
        print(f"R1 TX: {len(msg)} bytes -> {len(fr)} frames, loop {len(fr)*0.048:.2f} s, msgid {a.msgid}, gain {a.gain} dB", flush=True)
        wd = Path(a.workdir); fa, fb = wd / "H194E_R1_TX_A.c64", wd / "H194E_R1_TX_B.c64"; wa.tofile(fa); wb.tofile(fb)
        if a.write_only: return
        from gnuradio import gr, blocks
        import osmosdr
        tb = gr.top_block(); sink = osmosdr.sink(args="numchan=2 bladerf=0,nchan=2"); sink.set_sample_rate(C.FS)
        for ch in range(2): sink.set_center_freq(C.FC, ch); sink.set_gain(a.gain, ch)
        tb.connect(blocks.file_source(8, str(fa), True), (sink, 0)); tb.connect(blocks.file_source(8, str(fb), True), (sink, 1))
        try: tb.start(); print("R1 TRANSMISSION ACTIVE", flush=True); time.sleep(a.seconds)
        finally: tb.stop(); tb.wait()
        print("R1 TRANSMISSION COMPLETE")
    else:
        import H194E_V18Z37_MIMO_ANALYZE as Z, H194E_V18Z38_QKD_ANALYZE as A
        copies, nfr, cfo = decode_capture(A, Z, C, a.rx0, a.rx1)
        msg, info = assemble(copies, a.msgid); info.update(frames_synchronised=nfr, cfo_hz=round(float(cfo), 1), ok=msg is not None)
        print(info)
        if msg is not None and a.out: Path(a.out).write_bytes(msg); print(f"wrote {len(msg)} bytes to {a.out}")
        sys.exit(0 if msg is not None else 2)

if __name__ == "__main__":
    main()
