#!/usr/bin/env python3
"""H1.94E R2 -- BB84 in which BOTH the quantum layer and the public channel are carried by the SDR 2x2 MIMO link.
Quantum frames: Sender -> Receiver (spatial-qubit frames, as in B2). Public messages (Receiver bases, sifting mask + test bits,
verdict, reconciliation traffic) travel as CRC-protected radio frames (H194E_R1_RADIO_PIPE.py). Each PC has two antennas, so
the cables are moved between TX and RX ports whenever the direction changes (the program tells you when).
A tiny UDP 'doorbell' on the LAN carries only control tokens (tx_on / rx_done ok|retry / ready), never protocol data.
Run on both PCs from a folder holding: this file, H194E_R1_RADIO_PIPE.py, H194E_Z38_COMMON.py, H194E_V18Z37_MIMO_ANALYZE.py,
H194E_V18Z38_QKD_ANALYZE.py, H194E_V18Z34_CAPTURE.py, H194E_BB84_RF_DUAL_CAPTURE_V4.py, H194E_BPSK_TX_V18Z38_MIMO_QKD.py.
Export the patched gr-osmosdr paths first. Start the Receiver first, then the Sender.
  Sender  : python3 H194E_R2_RADIO_BB84.py --role sender   --peer RECEIVER_IP:6001 --listen 6002 --lib .
  Receiver: python3 H194E_R2_RADIO_BB84.py --role receiver --peer SENDER_IP:6002   --listen 6001 --lib .
--mode sim --yes --simdir DIR runs both roles on one machine with a synthetic channel (software test only)."""
import argparse, json, math, os, signal, socket, subprocess, sys, threading, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import H194E_R1_RADIO_PIPE as R1

def h2(x): return 0.0 if x <= 0 or x >= 1 else -x * math.log2(x) - (1 - x) * math.log2(1 - x)

class Bell:
    """LAN doorbell: reliable control tokens only (stop-and-wait with acks)."""
    def __init__(self, listen, peer):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.s.bind(("0.0.0.0", listen)); self.peer = peer
        self.seq = 0; self.seen = 0; self.acks = set(); self.q = []; self.n = 0
    def _take(self, d, addr):
        m = json.loads(d)
        if "ack" in m: self.acks.add(m["ack"]); return
        self.s.sendto(json.dumps({"ack": m["seq"]}).encode(), addr)
        if m["seq"] > self.seen: self.seen = m["seq"]; self.q.append(m)
    def send(self, obj):
        self.seq += 1; pkt = json.dumps(dict(seq=self.seq, **obj)).encode(); self.n += 1
        while self.seq not in self.acks:
            self.s.sendto(pkt, self.peer); self.s.settimeout(1.5)
            try:
                while self.seq not in self.acks: self._take(*self.s.recvfrom(65535))
            except socket.timeout: pass
    def recv(self, timeout=1800):
        t0 = time.time()
        while not self.q:
            if time.time() - t0 > timeout: raise TimeoutError("no message from the peer")
            self.s.settimeout(2)
            try: self._take(*self.s.recvfrom(65535))
            except socket.timeout: pass
        return self.q.pop(0)

class LabRadio:
    def __init__(self, a, C): self.a, self.C, self.proc = a, C, None
    def tx_start(self, kind, payload, msgid):
        a = self.a; lib = Path(a.lib).expanduser()
        if kind == "quantum":
            cmd = [sys.executable, str(lib / "H194E_BPSK_TX_V18Z38_MIMO_QKD.py"), "--seconds", "3600", "--frames", str(a.frames),
                   "--seed", str(a.seed), "--gain", str(a.gain_q), "--workdir", "."]
        else:
            f = Path(f"H194E_R2_{a.role}_msg.bin"); f.write_bytes(payload)
            cmd = [sys.executable, str(Path(__file__).resolve().parent / "H194E_R1_RADIO_PIPE.py"), "tx", "--lib", str(lib), "--file", str(f),
                   "--msgid", str(msgid), "--gain", str(a.gain_f if a.role == "sender" else a.gain_r), "--seconds", "3600"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        t0 = time.time()
        for line in self.proc.stdout:
            if "ACTIVE" in line: break
            if time.time() - t0 > 180: raise RuntimeError("transmitter did not start")
        threading.Thread(target=lambda: [None for _ in self.proc.stdout], daemon=True).start(); time.sleep(self.a.settle)
    def tx_stop(self):
        if self.proc is None: return
        self.proc.send_signal(signal.SIGINT)
        try: self.proc.wait(20)
        except subprocess.TimeoutExpired: self.proc.kill()
        self.proc = None
    def capture(self, tag):
        a = self.a
        r = subprocess.run([sys.executable, a.capture_script, "--state", "ON", "--tag", tag, "--seconds", str(a.cap_seconds)], capture_output=True, text=True)
        p = [f"H194E_V18Z34_{tag}_ON_RX{i}.c64" for i in range(2)]
        return p if all(os.path.exists(x) for x in p) else None
    def cleanup(self, p):
        if not self.a.keep:
            for x in p: os.path.exists(x) and os.remove(x)

class SimRadio:
    HF = np.array([[0.9 * np.exp(0.3j), 0.35 * np.exp(-1.2j)], [0.2 * np.exp(2.1j), 0.6 * np.exp(0.7j)]])
    HR = np.array([[0.7 * np.exp(-0.5j), 0.3 * np.exp(1.0j)], [0.25 * np.exp(-2.0j), 0.8 * np.exp(0.2j)]])
    def __init__(self, a, C): self.a, self.C, self.d = a, C, Path(a.simdir); self.d.mkdir(parents=True, exist_ok=True); self.n = 0
    def tx_start(self, kind, payload, msgid):
        if kind == "quantum":
            wa, wb = [], []
            for i in range(self.a.frames):
                sa, sb = self.C.frame_streams(self.a.seed, i); wa.append(self.C.to_waveform(sa, 0.14)); wb.append(self.C.to_waveform(sb, 0.14))
            wa, wb = np.concatenate(wa), np.concatenate(wb)
        else: wa, wb = R1.waveforms(self.C, R1.build_frames(payload, msgid), 0.14)
        tmp = self.d / f"tx_{self.a.role}.tmp.npz"; np.savez(tmp, wa=wa, wb=wb); os.replace(tmp, self.d / f"tx_{self.a.role}.npz")
    def tx_stop(self):
        f = self.d / f"tx_{self.a.role}.npz"; f.exists() and f.unlink()
    def capture(self, tag):
        a = self.a; peer = "receiver" if a.role == "sender" else "sender"; z = np.load(self.d / f"tx_{peer}.npz"); wa, wb = z["wa"], z["wb"]
        H, snr, cfo = (self.HF, a.sim_snr_f, 590.0) if peer == "sender" else (self.HR, a.sim_snr_r, -548.0)
        rng = np.random.default_rng(abs(hash((tag, a.seed))) % 2**32); L = len(wa); N = min(26_000_000, 3 * L + 400_000)
        off = int(rng.integers(0, 96000)); ba, bb = np.resize(np.roll(wa, -off), N), np.resize(np.roll(wb, -off), N)
        lo = np.exp(1j * rng.uniform(0, 6.28)); rot = np.exp(2j * np.pi * cfo * np.arange(N) / 2e6) * lo; p = []
        for i in range(2):
            s = (H[i, 0] * ba + H[i, 1] * bb) * rot; nv = np.mean(np.abs(s) ** 2) / 10 ** (snr / 10)
            s = s + np.sqrt(nv / 2) * (rng.standard_normal(N) + 1j * rng.standard_normal(N)); fn = str(self.d / f"{tag}_RX{i}.c64")
            s.astype(np.complex64).tofile(fn); p.append(fn)
        return p
    def cleanup(self, p):
        for x in p: os.path.exists(x) and os.remove(x)

def rx_measure(A, Z, C, rx0, rx1, rseed):
    """Quantum frames: sorted frame indices, Receiver bases and measured bits (same front end as B2)."""
    out, nfr, cfo = None, 0, 0.0
    x = [np.fromfile(p, dtype=np.complex64) for p in (rx0, rx1)]
    n = min(len(x[0]), len(x[1])); x = [v[A.SKIP:n] for v in x]
    cfo, _ = Z.estimate_cfo(x); ys = [Z.boxcar(Z.derotate(v, Z.F0 + cfo)) for v in x]
    metric = sum(np.abs(Z.pilot_correlation(y, Z.PA)) ** 2 for y in ys); peaks, med, top = Z.pick_peaks(metric)
    yks = [(n0, Z.frame_symbols(ys, n0)) for n0 in peaks]; yks = [(n0, k) for n0, k in yks if k is not None]
    if not yks: return None
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
    seen = {}
    for n0, yk in yks:
        est = A.decode_frame(yk, om, "MMSE")[2]; i = A.read_idx(est)
        if i is not None and i not in seen: seen[i] = est
    fl = sorted(seen); rb, rbit = [], []
    for i in fl:
        bb = np.random.RandomState([rseed, i]).randint(0, 2, C.N_Q).astype(np.uint8); rb.append(bb); rbit.append(A.measure(seen[i], bb))
    return np.array(fl, np.uint8), np.concatenate(rb), np.concatenate(rbit)

def sender_data(C, seed, fl):
    sb, sx = [], []
    for i in fl: b, v = C.sender_qubits(seed, int(i)); sx.append(b); sb.append(v)
    return np.concatenate(sb), np.concatenate(sx)

class Run:
    def __init__(self, a, bell, radio, C, A, Z):
        self.a, self.bell, self.radio, self.C, self.A, self.Z = a, bell, radio, C, A, Z
        self.mid = 0; self.rounds = 0; self.retries = 0; self.bytes = {"F": 0, "R": 0}; self.cur = None; self.t0 = time.time(); self.cap = 0
    def swap(self, d):
        if self.cur == d: return
        tx_side = (d == "F") == (self.a.role == "sender")
        txt = (f"[{self.a.role.upper()}] DIRECTION {'Sender -> Receiver' if d == 'F' else 'Receiver -> Sender'}: put BOTH of this PC's antennas on "
               f"{'TX1 and TX2' if tx_side else 'RX1 and RX2'} (50 ohm or nothing on the other two ports).")
        print("\n" + txt, flush=True)
        if not self.a.yes: input("   press Enter when done ... ")
        self.bell.send(dict(cmd="ready", dir=d)); m = self.bell.recv(); assert m["cmd"] == "ready" and m["dir"] == d, m; self.cur = d
    def exchange_tx(self, name, d, payload, quantum=False):
        parts = [None] if quantum else [payload[i:i + self.a.part_bytes] for i in range(0, max(1, len(payload)), self.a.part_bytes)]
        self.swap(d)
        for j, part in enumerate(parts):
            self.mid += 1; self.radio.tx_start("quantum" if quantum else "msg", part, self.mid); k = 0
            while True:
                self.bell.send(dict(cmd="tx_on", name=name, part=j, nparts=len(parts), msgid=self.mid, attempt=k)); self.rounds += 1
                r = self.bell.recv(); assert r["cmd"] == "rx_done", r
                if r["ok"]: break
                k += 1; self.retries += 1
                if k > self.a.max_retry: self.radio.tx_stop(); raise RuntimeError(f"{name}: too many retries: {r.get('info')}")
            self.radio.tx_stop(); self.bytes[d] += 0 if quantum else len(part)
        print(f"  [{self.a.role}] sent {name} ({'quantum frames' if quantum else str(len(payload)) + ' bytes'}, {len(parts)} part(s))", flush=True)
    def exchange_rx(self, name, d, quantum=False):
        self.swap(d); parts = []; res = None
        while True:
            m = self.bell.recv(); assert m["cmd"] == "tx_on" and m["name"] == name, m
            self.cap += 1; tag = f"R2{self.a.tag}{self.cap:03d}"; p = self.radio.capture(tag); ok, info = False, {}
            if p:
                if quantum:
                    res = rx_measure(self.A, self.Z, self.C, p[0], p[1], self.a.receiver_seed); ok = res is not None and len(res[0]) >= 0.95 * self.a.frames
                    info = dict(frames=0 if res is None else int(len(res[0])))
                else:
                    copies, nfr, cfo = R1.decode_capture(self.A, self.Z, self.C, p[0], p[1]); msg, info = R1.assemble(copies, m["msgid"]); ok = msg is not None
                self.radio.cleanup(p)
            info = {k: v for k, v in info.items() if k != "missing"}
            print(f"  [{self.a.role}] capture {tag}: ok={bool(ok)} {info}", flush=True)
            self.bell.send(dict(cmd="rx_done", ok=bool(ok), info=info))
            if ok and not quantum: parts.append(msg)
            if ok and m["part"] + 1 == m["nparts"]: break
        print(f"  [{self.a.role}] received {name}", flush=True)
        return res if quantum else b"".join(parts)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--role", choices=["sender", "receiver"], required=True)
    ap.add_argument("--lib", default="."); ap.add_argument("--peer", required=True); ap.add_argument("--listen", type=int, required=True)
    ap.add_argument("--mode", choices=["lab", "sim"], default="lab"); ap.add_argument("--simdir", default="/tmp/r2sim"); ap.add_argument("--yes", action="store_true")
    ap.add_argument("--frames", type=int, default=256); ap.add_argument("--seed", type=int, default=20261030); ap.add_argument("--receiver-seed", type=int, default=777)
    ap.add_argument("--gain-q", type=float, default=14); ap.add_argument("--gain-f", type=float, default=24); ap.add_argument("--gain-r", type=float, default=34); ap.add_argument("--cap-seconds", type=float, default=13)
    ap.add_argument("--capture-script", default="H194E_V18Z34_CAPTURE.py"); ap.add_argument("--part-bytes", type=int, default=4700)
    ap.add_argument("--max-retry", type=int, default=4); ap.add_argument("--eps", type=float, default=1e-6); ap.add_argument("--test-frac", type=float, default=0.1)
    ap.add_argument("--sim-snr-f", type=float, default=22); ap.add_argument("--sim-snr-r", type=float, default=16)
    ap.add_argument("--protocol", choices=["bb84", "bbm92"], default="bb84"); ap.add_argument("--settle", type=float, default=5.0); ap.add_argument("--keep", action="store_true"); ap.add_argument("--tag", default=time.strftime("%m%d%H%M")); ap.add_argument("--out", default=None); a = ap.parse_args()
    sys.path.insert(0, str(Path(a.lib).expanduser())); import H194E_Z38_COMMON as C
    import H194E_V18Z37_MIMO_ANALYZE as Z, H194E_V18Z38_QKD_ANALYZE as A
    ph, pp = a.peer.split(":"); bell = Bell(a.listen, (ph, int(pp))); radio = (SimRadio if a.mode == "sim" else LabRadio)(a, C)
    run = Run(a, bell, radio, C, A, Z); me = a.role == "sender"; bell.send(dict(cmd="hello", role=a.role)); assert bell.recv()["cmd"] == "hello"
    print(f"[{a.role}] peer connected; mode {a.mode}", flush=True); t0 = time.time()
    try:
        if me:
            run.exchange_tx("quantum", "F", None, quantum=True)
            msg = run.exchange_rx("bases", "R"); nf = len(msg) // 35; fl = np.frombuffer(msg[:nf], np.uint8)
            bases_r = np.unpackbits(np.frombuffer(msg[nf:], np.uint8))[:nf * C.N_Q]; sb, sx = sender_data(C, a.seed, fl); n = len(sb)
            keep = bases_r == sx; nk = int(keep.sum()); idx = np.random.default_rng(10).permutation(nk); nt = int(a.test_frac * nk)
            run.exchange_tx("mask+test", "F", np.packbits((sx if a.protocol == "bbm92" else keep).astype(np.uint8)).tobytes() + np.packbits(sb[keep][idx[:nt]]).tobytes())
            v = json.loads(run.exchange_rx("verdict", "R").decode())
            if v["abort"]: r = dict(role="sender", aborted=True, Qhat=v["Qhat"], qubits=n)
            else:
                lec = int(1.16 * h2(v["Qtrue_est"]) * (nk - nt)); run.exchange_tx("recon", "F", bytes(max(1, (lec + 7) // 8)))
                r = dict(role="sender", aborted=False, Qhat=v["Qhat"], key=max(0, math.floor((nk - nt) * (1 - h2(v["Qup"])) - lec - 2 * math.log2(1 / a.eps))), qubits=n, sifted=nk)
        else:
            fl, rb, rbit = run.exchange_rx("quantum", "F", quantum=True); n = len(rb)
            run.exchange_tx("bases", "R", fl.tobytes() + np.packbits(rb).tobytes())
            msg = run.exchange_rx("mask+test", "F"); ml = (n + 7) // 8; keep = np.unpackbits(np.frombuffer(msg[:ml], np.uint8))[:n].astype(bool)
            if a.protocol == "bbm92": keep = keep.astype(np.uint8) == rb
            nk = int(keep.sum()); idx = np.random.default_rng(10).permutation(nk); nt = int(a.test_frac * nk)
            kr = rbit[keep]; ks_t = np.unpackbits(np.frombuffer(msg[ml:], np.uint8))[:nt]
            Qhat = float(np.mean(ks_t != kr[idx[:nt]])); Qup = Qhat + math.sqrt(math.log(1 / a.eps) / (2 * nt))
            sb, sx = sender_data(C, a.seed, fl); qfull = float(np.mean(sb[keep] != kr))          # reference only (not used by the protocol)
            v = dict(Qhat=Qhat, Qup=Qup, abort=Qup > 0.11, Qtrue_est=Qhat); run.exchange_tx("verdict", "R", json.dumps(v).encode())
            r = dict(role="receiver", aborted=v["abort"], Qhat=Qhat, Q_all_sifted_reference=round(qfull, 5), qubits=n, sifted=nk)
            if not v["abort"]:
                run.exchange_rx("recon", "F"); r["key"] = max(0, math.floor((nk - nt) * (1 - h2(Qup)) - int(1.16 * h2(Qhat) * (nk - nt)) - 2 * math.log2(1 / a.eps)))
    finally: radio.tx_stop()
    r.update(protocol=a.protocol, wall_s=round(time.time() - t0, 1), radio_rounds=run.rounds, retries=run.retries, radio_msg_bytes=dict(run.bytes), lan_control_msgs=bell.n)
    print(json.dumps(r)); a.out and Path(a.out).write_text(json.dumps(r))

if __name__ == "__main__":
    main()
