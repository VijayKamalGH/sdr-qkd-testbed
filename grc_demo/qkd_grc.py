"""GNU Radio blocks for the SDR 2x2 MIMO spatial-qubit BB84 demo (GRC flowgraphs import this module).

QubitSource   : Sender. Builds the frozen frame (pilots, index word, 272 spatial qubits, guard) on two
                streams A and B (TX1, TX2), 2 MS/s complex baseband. Optional intercept-resend Eve.
QubitDecoder  : Receiver. Takes the two receive streams, runs the SAME processing steps as the frozen
                analyser H194E_V18Z38_QKD_ANALYZE.py on batches of frames (CFO, frame sync, channel from
                pilots, MMSE, frame index, random-basis measurement, sifting, QBER, Cascade, privacy
                amplification) and publishes numbers + the 'qubit plane' scatter for the GUI.
The frozen helper files (H194E_*.py, same folder) are imported unchanged.
"""
import os
import sys
import numpy as np
import threading as _th_dec
from gnuradio import gr

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)

import H194E_Z38_COMMON as C                       # frozen frame definition
import H194E_V18Z37_MIMO_ANALYZE as Z              # frozen DSP helpers
import H194E_P16B_BB84_CASCADE_UDP as P            # frozen Cascade + privacy amplification
import H194E_V18Z38_QKD_ANALYZE as A               # frozen analyser (decode_frame, measure, ...)

PERIOD = C.N_SYM * C.SPS                          # 96000 samples = one frame


class QubitSource(gr.sync_block):
    """Two complex outputs: stream A (TX1) and stream B (TX2). Frames are built on the fly."""

    def __init__(self, seed=20261030, amplitude=0.14, eve_rate=0.0, frames=256):
        gr.sync_block.__init__(self, name="Qubit source (Sender)", in_sig=None,
                               out_sig=[np.complex64, np.complex64])
        self.seed, self.amplitude, self.eve_rate, self.frames = int(seed), float(amplitude), float(eve_rate), int(frames)
        self.eve_rng = np.random.default_rng(self.seed ^ 0xE5E)
        self.idx = 0
        self.wa = self.wb = np.zeros(0, np.complex64)
        self.pos = 0

    def _next_frame(self):
        sa, sb = C.frame_streams(self.seed, self.idx % self.frames, self.eve_rate, self.eve_rng)
        self.wa, self.wb = C.to_waveform(sa, self.amplitude), C.to_waveform(sb, self.amplitude)
        self.idx += 1
        self.pos = 0

    def work(self, input_items, output_items):
        n = len(output_items[0])
        done = 0
        while done < n:
            if self.pos >= len(self.wa):
                self._next_frame()
            k = min(n - done, len(self.wa) - self.pos)
            output_items[0][done:done + k] = self.wa[self.pos:self.pos + k]
            output_items[1][done:done + k] = self.wb[self.pos:self.pos + k]
            self.pos += k
            done += k
        return n


class QubitDecoder(gr.sync_block):
    """Inputs: RX0, RX1 (complex). Outputs: [0] qubit-plane scatter (complex), then floats:
    [1] QBER %, [2] Q_upper %, [3] SINR A dB, [4] SINR B dB, [5] key bits, [6] frames decoded,
    [7] status (0 collecting, 1 key made, 2 aborted)."""

    def __init__(self, seed=20261030, receiver_seed=777, batch_frames=40, key_frames=200,
                 skip_first=0, reset=0, detector="MMSE", quiet=False, threaded=False):
        gr.sync_block.__init__(self, name="Qubit decoder (Receiver)",
                               in_sig=[np.complex64, np.complex64],
                               out_sig=[np.complex64] + [np.float32] * 7)
        self.seed, self.receiver_seed = int(seed), int(receiver_seed)
        self.batch_frames, self.key_frames = int(batch_frames), int(key_frames)
        self.skip_first, self.detector, self.quiet = int(skip_first), detector, bool(quiet)
        self.threaded = bool(int(threaded))             # live radio: decode in a background thread so the radio stream never blocks
        self._worker, self.dropped = None, 0
        self._reset_pending = False
        self.reset = int(reset)
        self.cons = np.zeros(C.N_Q, np.complex64)
        self.cpos = 0
        self.vals = [0.0] * 7
        self.log = []                                   # text lines (for tests / terminal)
        self._new_session()
        self.buf0, self.buf1, self.nbuf = [], [], 0
        self.skipped = 0

    # A GUI push button sets 1 on press and 0 on release; a short click can be missed by a polling loop, so latch it.
    @property
    def reset(self):
        return self._reset

    @reset.setter
    def reset(self, v):
        self._reset = int(v)
        if self._reset == 1:
            self._reset_pending = True

    # ------------------------------------------------------------------ session state
    def _new_session(self):
        w = getattr(self, "_worker", None)
        if w is not None and w is not _th_dec.current_thread() and w.is_alive():   # a manual reset waits for the running batch;
            w.join(timeout=10)                                                      # the automatic restart after a key runs inside it
        self.seen, self.snr, self.key_done = {}, {}, False

    def _say(self, s):
        self.log.append(s)
        if not self.quiet:
            print(s, flush=True)

    # ------------------------------------------------------------------ batch hand-over
    def _run_batch(self, x0, x1):
        try:
            self.process(x0, x1)
        except SystemExit as e:
            self._say(str(e))

    def _dispatch(self, x0, x1):
        if not self.threaded:
            self._run_batch(x0, x1)
            return
        if self._worker is not None and self._worker.is_alive():      # still busy: drop this batch, keep the radio stream flowing
            self.dropped += 1
            if self.dropped % 10 == 1:
                self._say("Receiver is busy: %d batch(es) skipped so far (the Sender repeats its frames, so this only delays the key)" % self.dropped)
            return
        self._worker = _th_dec.Thread(target=self._run_batch, args=(x0, x1), daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------ GNU Radio work
    def work(self, input_items, output_items):
        n = len(input_items[0])
        if self._reset_pending:
            self._reset_pending = False
            self._new_session()
            self.vals = [0.0] * 7
        a, b = input_items[0], input_items[1]
        if self.skipped < self.skip_first:                       # RX start-up transient
            d = min(n, self.skip_first - self.skipped)
            self.skipped += d
            a, b = a[d:], b[d:]
        if len(a):
            self.buf0.append(a.copy()); self.buf1.append(b.copy()); self.nbuf += len(a)
        if self.nbuf >= (self.batch_frames + 1) * PERIOD:
            x0, x1 = np.concatenate(self.buf0), np.concatenate(self.buf1)
            keep = 2 * PERIOD                                     # overlap: a frame cut at the end is seen again
            self.buf0, self.buf1, self.nbuf = [x0[-keep:]], [x1[-keep:]], keep
            self._dispatch(x0, x1)
        # outputs: scatter cycles through the last frame's qubit vectors
        idx = (self.cpos + np.arange(n)) % len(self.cons)
        output_items[0][:] = self.cons[idx]
        self.cpos = (self.cpos + n) % len(self.cons)
        for k, v in enumerate(self.vals):
            output_items[1 + k][:] = v
        return n

    # ------------------------------------------------------------------ the analyser steps
    def _find_frames(self, x0, x1):
        """Frame search shared by the key and message Receivers: CFO, pilot sync, pilot phase rate, repeat filter, noise covariance."""
        x = [x0, x1]
        cfo, sharp = Z.estimate_cfo(x)
        ys = [Z.boxcar(Z.derotate(v, Z.F0 + cfo)) for v in x]
        metric = sum(np.abs(Z.pilot_correlation(y, Z.PA)) ** 2 for y in ys)
        peaks, med, top = Z.pick_peaks(metric)
        yks = [(n0, Z.frame_symbols(ys, n0)) for n0 in peaks]
        yks = [(n0, k) for n0, k in yks if k is not None]
        if not yks:
            self._say("No frames found in this batch (check gains / noise level).")
            return None, None
        om = float(np.median([Z.pilot_om(k) for _, k in yks]))
        hp = [(n0, np.mean(k[:, :C.N_PILOT] * Z.PA, axis=1)) for n0, k in yks]
        zacc, npair = 0j, 0
        for (na, ha), (nb, hb) in zip(hp[:-1], hp[1:]):
            if abs((nb - na) - Z.PERIOD) <= 600:
                zacc += np.sum(np.conj(ha) * hb); npair += 1
        if npair >= 10:
            om = float(np.angle(zacc) / C.N_SYM)
        if len(yks) > 1:
            pos = np.array([n0 for n0, _ in yks]); keepf = []
            for p in pos:
                d = np.abs(pos - p); m = np.rint(d / Z.PERIOD)
                keepf.append(bool((((m >= 1) & (m <= 4)) & (np.abs(d - m * Z.PERIOD) <= 600)).any()))
            yks = [t for t, k in zip(yks, keepf) if k]
        A.CHAT = A._fit_chat(yks, om) if yks else None          # full receive-noise covariance (as the analyser)
        return yks, om

    def process(self, x0, x1):
        yks, om = self._find_frames(x0, x1)
        if yks is None:
            return
        for n0, yk in yks:
            H, noise, est = A.decode_frame(yk, om, self.detector)
            i = A.read_idx(est)
            if i is None or i in self.seen:
                continue
            self.seen[i] = est
            self.snr[i] = (H, noise, None if A.CHAT is None else A.CHAT.copy())
            self.cons = (est[0, C.N_IDX:].real + 1j * est[1, C.N_IDX:].real).astype(np.complex64)
        self._stats()
        if len(self.seen) >= 256:                                # session complete: start a new one
            self._new_session()

    def _stats(self):
        seen = self.seen
        if not seen:
            return
        AB, BB, BAS = [], [], []
        for i, e in sorted(seen.items()):
            abas, abit = C.sender_qubits(self.seed, i)
            bbas = np.random.RandomState([self.receiver_seed, i]).randint(0, 2, C.N_Q).astype(np.uint8)
            bbit = A.measure(e, bbas)
            s = abas == bbas
            AB.append(abit[s]); BB.append(bbit[s]); BAS.append(abas[s])
        ka, kb = np.concatenate(AB), np.concatenate(BB)
        q = float(np.mean(ka != kb))
        sn = []
        for H, noise, chat in self.snr.values():
            R = np.diag(noise) if chat is None else np.sqrt(noise)[:, None] * chat * np.sqrt(noise)[None, :]
            Pm = np.linalg.inv(np.eye(2) + H.conj().T @ np.linalg.inv(R) @ H)
            sn.append([1.0 / Pm[k, k].real - 1.0 for k in range(2)])
        sn = np.mean(np.array(sn), axis=0)
        sa, sb = (10 * np.log10(max(v, 1e-12)) for v in sn)
        m, nt = len(ka), max(1, int(0.1 * len(ka)))
        rng = np.random.default_rng(5); idx = rng.permutation(m); t = idx[:nt]
        qest = float(np.mean(ka[t] != kb[t])); qup = qest + np.sqrt(np.log(1e6) / (2 * nt))
        status = self.vals[6] if self.key_done else 0.0
        key = self.vals[4] if self.key_done else 0.0
        self.vals = [100 * q, 100 * qup, float(sa), float(sb), key, float(len(seen)), status]
        if not self.key_done and len(seen) >= self.key_frames:
            self.key_done = True
            if qup > 0.11:
                self.vals[4], self.vals[6] = 0.0, 2.0
                self._say(f"ABORT: Q_upper {100 * qup:.2f}% > 11% -> no secret key | QBER {100 * q:.2f}% | frames {len(seen)}")
            else:
                k = idx[nt:]
                Aa, Bb = ka[k].astype(np.uint8), kb[k].astype(np.uint8)
                Bc, leak = P.cascade(Aa, Bb, max(qest, 0.01), np.random.default_rng(9), passes=6)
                ok = bool(np.array_equal(P.toeplitz_pa(Aa, 64, np.random.default_rng(11)), P.toeplitz_pa(Bc, 64, np.random.default_rng(11))))
                leak += 64
                L = int(max(0, np.floor(len(Aa) * (1 - P.h(qup)) - leak - 2 * np.log2(1e6))))
                if not ok:
                    L = 0
                sA = P.toeplitz_pa(Aa, L, np.random.default_rng(5)); sB = P.toeplitz_pa(Bc, L, np.random.default_rng(5))
                eq = bool(np.array_equal(sA, sB))
                self.vals[4], self.vals[6] = float(L), 1.0
                self._say(f"KEY: frames {len(seen)} | QBER {100 * q:.2f}% | SINR A {sa:+.1f} B {sb:+.1f} dB | "
                          f"final key {L} bits | Sender==Receiver: {eq}")


# ====================================================================== other demo blocks
import json as _json
import subprocess as _sp
import threading as _th
import time as _time


class _SlowSource(gr.sync_block):
    """Helper: float-output source that emits a few samples per call (slow, for status values)."""
    n_out = 1

    def __init__(self, name):
        gr.sync_block.__init__(self, name=name, in_sig=None, out_sig=[np.float32] * self.n_out)
        self.vals = [0.0] * self.n_out

    def work(self, input_items, output_items):
        _time.sleep(0.05)
        n = min(len(output_items[0]), 64)
        for k, v in enumerate(self.vals):
            output_items[k][:n] = v
        return n


class UdpRunner(_SlowSource):
    """Demo 1: runs the frozen public-channel script (H194E_PB_UDP_BB84.py) as Sender or Receiver.
    Outputs: Qhat %, key bits, frames sent, frames lost / timeouts, status (0 idle,1 running,2 key made,3 aborted)."""
    n_out = 5

    def __init__(self, role="sender", peer="127.0.0.1:5005", listen=5006, n=40000, qch=0.02, q_eve=0.0,
                 p_loss=0.0, go=0):
        _SlowSource.__init__(self, "UDP public channel (" + str(role) + ")")
        self.role, self.peer, self.listen, self.n = role, peer, int(listen), int(n)
        self.qch, self.q_eve, self.p_loss = float(qch), float(q_eve), float(p_loss)
        self._pending = False
        self.go = int(go)
        self.log = []
        self.running = False

    @property
    def go(self):
        return self._go

    @go.setter
    def go(self, v):
        self._go = int(v)
        if self._go == 1:
            self._pending = True

    def _run(self):
        self.running = True
        self.vals = [0.0, 0.0, 0.0, 0.0, 1.0]
        cmd = [sys.executable, os.path.join(_HERE, "H194E_PB_UDP_BB84.py"), "--role", self.role, "--listen", str(self.listen),
               "--peer", self.peer, "--n", str(self.n), "--qch", str(self.qch), "--q-eve", str(self.q_eve)]
        if self.p_loss > 0 and self.role == "receiver":          # frame loss is emulated on the Receiver only
            cmd += ["--p-loss", str(self.p_loss)]
        try:
            pr = _sp.run(cmd, capture_output=True, text=True, timeout=600)
            out = pr.stdout.strip().splitlines()
            if not out:
                print("UDP demo: the script printed no result. Exit code", pr.returncode, flush=True)
                print("Command:", " ".join(cmd), flush=True)
                print("Error text:", (pr.stderr or "(none)")[-1500:], flush=True)
                raise RuntimeError("no result from script")
            r = _json.loads(out[-1])
            self.log.append(out[-1])
            print(out[-1], flush=True)
            if r.get("aborted"):
                self.vals = [100 * r["Qhat"], 0.0, float(r.get("frames", r.get("frames_tx", 0))), float(r.get("timeouts", r.get("frames_lost", 0))), 3.0]
            else:
                self.vals = [100 * r["Qhat"], float(r["key"]), float(r.get("frames", r.get("frames_tx", 0))), float(r.get("timeouts", r.get("frames_lost", 0))), 2.0]
        except Exception as e:                                    # peer not started, timeout, ...
            self.log.append("error: %r" % (e,)); print("UDP demo error:", e, flush=True)
            self.vals = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.running = False

    def work(self, input_items, output_items):
        if self._pending:
            self._pending = False
            if not self.running:
                _th.Thread(target=self._run, daemon=True).start()
        return _SlowSource.work(self, input_items, output_items)


class ResultsTable(_SlowSource):
    """Demo 3: shows one stored fresh-sweep capture (W1/W2 table) selected by index."""
    n_out = 7

    def __init__(self, idx=0, table="w1w2_table.json"):
        _SlowSource.__init__(self, "Sweep results (W1/W2)")
        self.idx, self.table = int(idx), table
        rows = []
        d = _json.load(open(os.path.join(_HERE, table)))
        for k in d:
            for r in d[k]:
                rows.append(r)
        self.rows = rows
        self._set()

    def _set(self):
        r = self.rows[int(self.idx) % len(self.rows)]
        self.vals = [float(r["tag"][3:]), float(r["gain"]), float(r["sinr"]), 100 * float(r["qm"]), 100 * float(r["qz"]),
                     float(r["key_m"]), float(r["key_z"])]

    def work(self, input_items, output_items):
        self._set()
        return _SlowSource.work(self, input_items, output_items)


class BladeRFPlayer(_SlowSource):
    """Live Sender on the lab LAPTOPS: plays the pre-generated waveform through bladeRF-cli (the path that works there).
    Runs `bash ~/txfiles/tx.sh GAIN` repeatedly while run = 1. Outputs: runs done, runs failed, status."""
    n_out = 3

    def __init__(self, gain=30, run=0, script="~/txfiles/tx.sh"):
        _SlowSource.__init__(self, "bladeRF-cli player (Sender laptop)")
        self.gain, self.run, self.script = int(gain), int(run), os.path.expanduser(script)
        self.done = self.failed = 0
        self.busy = False
        self.vals = [0.0, 0.0, 0.0]

    def _loop(self):
        self.busy = True
        while self.run == 1:
            self.vals[2] = 1.0
            try:
                out = _sp.run(["bash", self.script, str(self.gain)], capture_output=True, text=True, timeout=90)
                bad = ("LIBUSB_ERROR" in out.stdout + out.stderr) or ("core dumped" in out.stdout + out.stderr)
                print(out.stdout.strip(), flush=True)
            except Exception as e:
                bad = True; print("player error:", e, flush=True)
            self.done += 1; self.failed += int(bad)
            self.vals[0], self.vals[1] = float(self.done), float(self.failed)
        self.vals[2] = 0.0
        self.busy = False

    def work(self, input_items, output_items):
        if self.run == 1 and not self.busy:
            _th.Thread(target=self._loop, daemon=True).start()
        return _SlowSource.work(self, input_items, output_items)


class CaptureReplay(gr.sync_block):
    """Demo 4 source: plays two stored capture files (RX0, RX1; complex64, 2 MS/s) in a loop. A missing file does not
    crash the flowgraph: the block waits and prints a message, so the file names can be typed in the GUI."""

    def __init__(self, rx0_file="H194E_V18Z34_SWW203_ON_RX0.c64", rx1_file="H194E_V18Z34_SWW203_ON_RX1.c64"):
        gr.sync_block.__init__(self, name="Capture replay", in_sig=None, out_sig=[np.complex64, np.complex64])
        self.rx0_file, self.rx1_file = rx0_file, rx1_file
        self._open_names = None
        self.maps = None
        self.pos = 0
        self._warned = None
        self._t_fail = 0.0

    def _try_open(self):
        names = (self.rx0_file, self.rx1_file)
        if names == self._open_names:
            if self.maps is None and _time.time() - self._t_fail > 3:      # retry a failed open every 3 s
                self._open_names = None
            else:
                return self.maps is not None
        self._open_names, self.maps, self.pos = names, None, 0
        try:
            m = [np.memmap(os.path.expanduser(p), dtype=np.complex64, mode="r") for p in names]
            self.maps, self.n = m, min(len(m[0]), len(m[1]))
            self._say("Replay: opened %s and %s (%d samples, %.1f s)" % (names[0], names[1], self.n, self.n / 2e6))
        except Exception as e:
            self._t_fail = _time.time()
            if self._warned != names:
                self._say("Replay: cannot open the capture files (%s). Put them in this folder and type their names." % (e,))
                self._warned = names
        return self.maps is not None

    def _say(self, s):
        print(s, flush=True)

    def work(self, input_items, output_items):
        if not self._try_open():
            _time.sleep(0.3)
            return 0
        n = len(output_items[0]); done = 0
        while done < n:
            k = min(n - done, self.n - self.pos)
            for c in (0, 1):
                output_items[c][done:done + k] = self.maps[c][self.pos:self.pos + k]
            self.pos = (self.pos + k) % self.n
            done += k
        return n


# ====================================================================== Demo 6: public-channel message
import struct as _struct
import zlib as _zlib

MSG_DATA = 30                          # data bytes per radio frame (+4 bytes CRC32 = 34 bytes = the 272 qubit symbols of one frame)
MSG_MAXF = 256
MSG_STATE = {"t0": {}}                 # simulation only: when the Sender started each message (msgid -> time.time())


def msg_build_frames(msg, msgid):
    """Same framing as the frozen R1 radio pipe: b'R1' + msgid(2) + length(4) + text, padded to 30-byte chunks, CRC32 per chunk."""
    body = b"R1" + _struct.pack("!HI", msgid & 0xFFFF, len(msg)) + msg
    body += bytes((-len(body)) % MSG_DATA)
    n = len(body) // MSG_DATA
    if n > MSG_MAXF:
        raise ValueError("message too long")
    out = []
    for i in range(n):
        d = body[i * MSG_DATA:(i + 1) * MSG_DATA]
        out.append(d + _struct.pack("!I", _zlib.crc32(bytes([msgid & 255, i]) + d)))
    return out


def msg_frame_ok(raw, idx, msgid):
    return len(raw) == MSG_DATA + 4 and _zlib.crc32(bytes([msgid & 255, idx]) + raw[:MSG_DATA]) == _struct.unpack("!I", raw[MSG_DATA:])[0]


def msg_streams(idx, frame34, bit0_offset=0):
    """Z basis: bit 0 -> |0> on TX1 (stream A), bit 1 -> |1> on TX2 (stream B); pilots and index word as in every frame."""
    bits = np.unpackbits(np.frombuffer(frame34, np.uint8))
    pa, pb = C.pilots()
    sa, sb = np.zeros(C.N_SYM), np.zeros(C.N_SYM)
    sa[:C.N_PILOT], sb[C.N_PILOT:2 * C.N_PILOT] = pa, pb
    sa[C.I0:C.Q0] = C.idx_symbols(idx)
    sa[C.Q0:C.Q1] = (bits == 0)
    sb[C.Q0:C.Q1] = (bits == 1)
    return sa, sb


class MessageSource(gr.sync_block):
    """Sender: sends a text as chunks of 30 bytes + CRC32, one chunk per 48 ms frame, and repeats the whole message in a loop."""

    def __init__(self, text="hello", amplitude=0.14, send=0):
        gr.sync_block.__init__(self, name="Message source (Sender)", in_sig=None,
                               out_sig=[np.complex64, np.complex64])
        self.amplitude = float(amplitude)
        self.msgid = 0
        self.wf = []                     # list of (wa, wb) per chunk
        self.ci, self.pos = 0, 0
        self._pending = True
        self._send = 0
        self._text = ""
        self.text = text
        self.send = send

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, v):
        v = str(v).encode("utf-8")[:240].decode("utf-8", "ignore")
        self._text = v
        self._pending = True

    @property
    def send(self):
        return self._send

    @send.setter
    def send(self, v):                   # latching: a short click on a push button is enough
        self._send = int(v)
        if self._send == 1:
            self._pending = True

    def _rebuild(self):
        self._pending = False
        self.msgid = (self.msgid + 1) & 255
        fr = msg_build_frames(self._text.encode("utf-8"), self.msgid)
        self.wf = []
        for i, f in enumerate(fr):
            sa, sb = msg_streams(i, f)
            self.wf.append((C.to_waveform(sa, self.amplitude), C.to_waveform(sb, self.amplitude)))
        self.ci, self.pos = 0, 0
        MSG_STATE["t0"][self.msgid] = _time.time()

    def work(self, input_items, output_items):
        n = len(output_items[0])
        done = 0
        while done < n:
            if not self.wf or (self._pending and self.pos == 0):
                self._rebuild()
            wa, wb = self.wf[self.ci]
            k = min(n - done, len(wa) - self.pos)
            output_items[0][done:done + k] = wa[self.pos:self.pos + k]
            output_items[1][done:done + k] = wb[self.pos:self.pos + k]
            self.pos += k
            done += k
            if self.pos >= len(wa):
                self.pos = 0
                self.ci = (self.ci + 1) % len(self.wf)
        return n


class MessageDecoder(QubitDecoder):
    """Receiver: same front end as the key Receiver (pilot sync, MMSE), then reads each frame in the Z basis, checks the CRC32,
    keeps the first good copy of every chunk and assembles the text. Float outputs:
    [1] frames synchronised, [2] good chunks, [3] bad-CRC copies, [4] message length (bytes), [5] status (0 waiting, 1 receiving, 2 received),
    [6] delay s (simulation only, 0 on two computers), [7] SINR dB (mean of A and B)."""

    def __init__(self, batch_frames=3, skip_first=0, reset=0, detector="MMSE", quiet=False, threaded=False):
        QubitDecoder.__init__(self, batch_frames=batch_frames, skip_first=skip_first, reset=reset,
                              detector=detector, quiet=quiet, threaded=threaded)
        self.shown = "(waiting for a message)"
        self.t_start = None

    def _new_session(self):
        w = getattr(self, "_worker", None)
        if w is not None and w is not _th_dec.current_thread() and w.is_alive():
            w.join(timeout=10)
        self.good, self.nsync, self.nbad, self.cur = {}, 0, 0, None
        self.seen, self.snr, self.key_done = {}, {}, False
        self.shown = "(waiting for a message)"
        self.vals = [0.0] * 7
        self.done_delay = 0.0
        self.last_mid = 0
        self.t_reset = _time.time()      # delay is counted from the later of: Sender start, receiver clear

    def process(self, x0, x1):
        yks, om = self._find_frames(x0, x1)
        if yks is None:
            return
        zero = np.zeros(C.N_Q, np.uint8)
        sn = []
        for n0, yk in yks:
            H, noise, est = A.decode_frame(yk, om, self.detector)
            i = A.read_idx(est)
            R = np.diag(noise) if A.CHAT is None else np.sqrt(noise)[:, None] * A.CHAT * np.sqrt(noise)[None, :]
            Pm = np.linalg.inv(np.eye(2) + H.conj().T @ np.linalg.inv(R) @ H)
            sn.append(np.mean([1.0 / Pm[k, k].real - 1.0 for k in range(2)]))
            self.nsync += 1
            if i is None:
                self.nbad += 1
                continue
            self.cons = (est[0, C.N_IDX:].real + 1j * est[1, C.N_IDX:].real).astype(np.complex64)
            raw = np.packbits(A.measure(est, zero)).tobytes()
            mid = None
            for m in [self.last_mid] + list(range(256)):
                if msg_frame_ok(raw, i, m):
                    mid = m
                    break
            if mid is None:
                self.nbad += 1
                continue
            if mid != self.last_mid:                              # a new message: start over
                self.good, self.last_mid, self.nbad = {}, mid, 0
                self.key_done, self.done_delay, self.nsync = False, 0.0, 0
                self.shown = "(receiving ...)"
            self.good.setdefault(i, raw[:MSG_DATA])
        self._summarise(float(10 * np.log10(max(np.mean(sn), 1e-12))) if sn else 0.0)

    def _summarise(self, sinr):
        g = self.good
        length, status, delay = 0, 0, 0.0
        if g:
            status = 1
            if 0 in g and g[0][:2] == b"R1":
                mid, length = _struct.unpack("!HI", g[0][2:8])
                n = -(-(8 + length) // MSG_DATA)
                if all(i in g for i in range(n)):
                    body = b"".join(g[i] for i in range(n))[8:8 + length]
                    self.shown = body.decode("utf-8", "replace")
                    status = 2
                    t0 = MSG_STATE["t0"].get(self.last_mid)
                    t0 = None if t0 is None else max(t0, self.t_reset)
                    if self.done_delay == 0.0 and t0 is not None:
                        self.done_delay = _time.time() - t0
                    delay = self.done_delay
                    if self.nsync and not self.key_done:
                        self.key_done = True
                        self._say(f'MESSAGE RECEIVED at {_time.strftime("%H:%M:%S")}.{int(_time.time() * 1000) % 1000:03d}: "{self.shown}" | {length} bytes in {n} chunks | frames {self.nsync} | bad CRC copies {self.nbad}'
                                  + (f" | time since the Sender started it {delay:.2f} s (simulation clock)" if delay else ""))
        self.vals = [float(self.nsync), float(len(g)), float(self.nbad), float(length), float(status), float(delay), sinr]


class MessagePlayer(_SlowSource):
    """Live message Sender on the lab LAPTOP: builds the message waveform (same frame format as the lab waveform), writes it to
    ~/txfiles/MSG_AB.bin in the same file format as ~/txfiles/TX_AB.bin, and plays it with bladeRF-cli (same commands as tx2x2.cli)
    for 30 s. A transmission starts when 'send' is pressed. Outputs: transmissions done, failed, status (0 idle, 1 preparing, 2 transmitting),
    chunks in the message, message loop length (s)."""
    n_out = 5

    def __init__(self, text="hello", gain=30, send=0, amplitude=0.14, txdir="~/txfiles", seconds=30):
        _SlowSource.__init__(self, "Message player (Sender laptop)")
        self.text, self.gain, self.amplitude = str(text), int(gain), float(amplitude)
        self.txdir, self.seconds = os.path.expanduser(txdir), int(seconds)
        self.done = self.failed = 0
        self.busy = False
        self._send, self._pending = 0, False
        self.msgid = 0
        self.vals = [0.0] * 5
        self.send = send

    @property
    def send(self):
        return self._send

    @send.setter
    def send(self, v):                     # latching: a short click is enough
        self._send = int(v)
        if self._send == 1:
            self._pending = True

    def _scale_and_order(self):
        """Compare the lab files TX_A.c64 / TX_AB.bin (same start): scale from float to int16 and the column order."""
        pa, pb, pk = (os.path.join(self.txdir, n) for n in ("H194E_Z38_TX_A.c64", "H194E_Z38_TX_B.c64", "TX_AB.bin"))
        try:
            a = np.fromfile(pa, np.complex64, count=40000)
            b = np.fromfile(pb, np.complex64, count=40000)
            x = np.fromfile(pk, np.int16, count=160000).reshape(-1, 4).astype(np.float64)
            m = min(len(a), len(b), len(x))
            ref = [a.real[:m], a.imag[:m], b.real[:m], b.imag[:m]]
            if min(np.max(np.abs(r)) for r in ref) == 0:
                raise ValueError("lab c64 file starts with zeros")
            best = None
            for order in ([0, 1, 2, 3], [2, 3, 0, 1]):
                sc = [float(np.dot(x[:m, k], ref[order[k]]) / np.dot(ref[order[k]], ref[order[k]])) for k in range(4)]
                res = sum(float(np.sum((x[:m, k] - sc[k] * ref[order[k]]) ** 2)) for k in range(4)) / max(1.0, sum(float(np.sum(x[:m, k] ** 2)) for k in range(4)))
                if best is None or res < best[0]:
                    best = (res, order, float(np.mean(sc)))
            res, order, sc = best
            print("player: TX_AB.bin = int16 columns [A_I A_Q B_I B_Q], scale %.1f, column order %s, relative mismatch %.2e" % (sc, order, res), flush=True)
            if res > 1e-2:
                print("player: WARNING mismatch is large; check the format of TX_AB.bin", flush=True)
            return sc, order
        except Exception as e:
            print("player: could not compare with TX_AB.bin (%s); using scale 2047 and order A,B" % e, flush=True)
            return 2047.0, [0, 1, 2, 3]

    def build(self, text=None, path=None):
        """Write the message waveform; returns (file, chunks, loop seconds)."""
        text = self.text if text is None else text
        self.msgid = (self.msgid + 1) & 255
        fr = msg_build_frames(str(text).encode("utf-8")[:240], self.msgid)
        wa, wb = [], []
        for i, f in enumerate(fr):
            sa, sb = msg_streams(i, f)
            wa.append(C.to_waveform(sa, self.amplitude)); wb.append(C.to_waveform(sb, self.amplitude))
        k = max(1, -(-100 // len(fr)))                       # repeat the message so the file holds at least 100 frames
        wa = np.tile(np.concatenate(wa), k); wb = np.tile(np.concatenate(wb), k)
        sc, order = self._scale_and_order()
        cols = [wa.real, wa.imag, wb.real, wb.imag]
        out = np.empty((len(wa), 4), np.int16)
        for j in range(4):
            out[:, j] = np.clip(np.rint(cols[order[j]] * sc), -2047, 2047).astype(np.int16)
        path = path or os.path.join(self.txdir, "MSG_AB.bin")
        out.tofile(path)
        return path, len(fr), len(fr) * 0.048

    def _once(self):
        self.busy = True
        try:
            self.vals[2] = 1.0
            path, n, loop = self.build()
            self.vals[3], self.vals[4] = float(n), float(loop)
            cli = os.path.join(self.txdir, "msg_run.cli")
            open(cli, "w").write("set frequency tx 915M\nset samplerate tx 2M\nset gain tx1 %d\nset gain tx2 %d\n"
                                 "tx config file=%s format=bin repeat=0 channel=1,2\ntx start\ntx wait %ds\ntx stop\n"
                                 % (self.gain, self.gain, path, self.seconds))
            self.vals[2] = 2.0
            print("Message Sender start %s.%03d  msgid %d  \"%s\"  (%d chunk(s), loop %.2f s, gain %d dB)"
                  % (_time.strftime("%H:%M:%S"), int(_time.time() * 1000) % 1000, self.msgid, self.text, n, loop, self.gain), flush=True)
            out = _sp.run("timeout -s KILL %d bladeRF-cli -s %s 2>&1 | tail -n 3" % (self.seconds + 20, cli), shell=True,
                          capture_output=True, text=True, timeout=self.seconds + 40)
            bad = ("LIBUSB_ERROR" in out.stdout) or ("core dumped" in out.stdout) or ("rror" in out.stdout)
            print(out.stdout.strip(), flush=True)
            print("Message Sender end %s" % _time.strftime("%H:%M:%S"), flush=True)
        except Exception as e:
            bad = True; print("player error:", e, flush=True)
        self.done += 1; self.failed += int(bad)
        self.vals[0], self.vals[1], self.vals[2] = float(self.done), float(self.failed), 0.0
        self.busy = False

    def work(self, input_items, output_items):
        if self._pending and not self.busy:
            self._pending = False
            _th.Thread(target=self._once, daemon=True).start()
        return _SlowSource.work(self, input_items, output_items)
