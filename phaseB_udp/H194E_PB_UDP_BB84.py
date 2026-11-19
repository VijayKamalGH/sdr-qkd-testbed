#!/usr/bin/env python3
"""Phase B: BB84 with the public channel carried over real UDP between a Sender and a Receiver process."""
import argparse, math, socket, struct, time, json
import numpy as np

PAY = 34                                   # bytes per frame = 272 bits
HDR = struct.Struct("!BIHH")               # type(0 data,1 ack), msg id, seq, nseq

class Udp:
    def __init__(self, listen, peer, t_frame, p_loss, seed, speedup=1.0):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); self.s.bind(("0.0.0.0", listen)); self.peer = peer
        self.tf = t_frame / speedup; self.p = p_loss; self.rng = np.random.default_rng(seed); self.mid = 0
        self.frames_tx = 0; self.frames_lost = 0; self.bits = 0; self.timeouts = 0
    def send(self, data: bytes):
        self.mid += 1; n = max(1, math.ceil(len(data) / PAY)); self.bits += 8 * len(data)
        for q in range(n):
            chunk = data[q * PAY:(q + 1) * PAY]
            while True:
                time.sleep(self.tf)                                     # frame airtime (SDR link)
                self.s.sendto(HDR.pack(0, self.mid, q, n) + chunk, self.peer); self.frames_tx += 1
                dl = time.time() + max(0.05, 3 * self.tf); ok = False
                while not ok:                                           # wait out the full timeout; stale/duplicate acks are ignored
                    rem = dl - time.time()
                    if rem <= 0: break
                    self.s.settimeout(rem)
                    try:
                        pkt, _ = self.s.recvfrom(2048); t, m, sq, _ = HDR.unpack(pkt[:HDR.size])
                        ok = (t == 1 and m == self.mid and sq == q)
                    except socket.timeout: break
                if ok: break
                self.timeouts += 1
    def recv(self):
        got, n, mid = {}, None, None
        self.s.settimeout(30)
        while n is None or len(got) < n:
            pkt, addr = self.s.recvfrom(2048); t, m, q, nn = HDR.unpack(pkt[:HDR.size])
            if t != 0: continue
            if self.rng.random() < self.p: self.frames_lost += 1; continue     # emulated frame loss (no ack -> sender resends)
            self.s.sendto(HDR.pack(1, m, q, nn), addr)
            if mid is not None and m < mid: continue                 # late duplicate of an earlier message
            if mid is None or m != mid: got, mid, n = {}, m, nn
            got[q] = pkt[HDR.size:]
        return b"".join(got[i] for i in range(n))

def h2(x): return 0.0 if x <= 0 or x >= 1 else -x*math.log2(x)-(1-x)*math.log2(1-x)
def quantum(n, q, qch, seed):
    rs = np.random.default_rng(seed); sb, sx = rs.integers(0,2,n), rs.integers(0,2,n)
    hit = rs.random(n) < q; eb = rs.integers(0,2,n)
    bit = np.where(hit, np.where(eb == sx, sb, rs.integers(0,2,n)), sb) ^ (rs.random(n) < qch)
    rb = rs.integers(0,2,n); res = np.where(rb == sx, bit, rs.integers(0,2,n)); return sb, sx, rb, res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--role", choices=["sender", "receiver"], required=True)
    ap.add_argument("--listen", type=int, default=None); ap.add_argument("--peer", default=None)
    ap.add_argument("--n", type=int, default=40000); ap.add_argument("--qch", type=float, default=0.0); ap.add_argument("--q-eve", type=float, default=0.0)
    ap.add_argument("--p-loss", type=float, default=0.0); ap.add_argument("--t-frame", type=float, default=0.048)
    ap.add_argument("--speedup", type=float, default=1.0); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--eps", type=float, default=1e-6); ap.add_argument("--test-frac", type=float, default=0.1); a = ap.parse_args()
    if not a.peer: ap.error("--peer HOST:PORT is required for both roles")
    ph, pp = a.peer.split(":")
    me = a.role == "sender"; listen = a.listen if a.listen else (5006 if me else 5005)
    u = Udp(listen, (ph, int(pp)), a.t_frame, a.p_loss, a.seed + (1 if me else 2), a.speedup)
    sb, sx, rb, res = quantum(a.n, a.q_eve, a.qch, a.seed); t0 = time.time()
    if me:                                                    # ---- Sender
        bases_r = np.unpackbits(np.frombuffer(u.recv(), np.uint8))[:a.n]          # 1. receiver bases
        keep = bases_r == sx; u.send(np.packbits(keep.astype(np.uint8)).tobytes())  # 2. sifting mask
        nk = int(keep.sum()); idx = np.random.default_rng(a.seed + 9).permutation(nk); nt = int(a.test_frac * nk)
        ks = sb[keep]; u.send(np.packbits(ks[idx[:nt]]).tobytes())                   # 3. sender bits on the test subset
        verdict = json.loads(u.recv().decode()); Qup = verdict["Qup"]; Qhat = verdict["Qhat"]
        if verdict["abort"]: print(json.dumps(dict(role="sender", aborted=True, Qhat=Qhat, wall_s=round(time.time()-t0, 2), frames=u.frames_tx, timeouts=u.timeouts))); return
        lec = int(1.16 * h2(verdict["Qtrue_est"]) * (nk - nt)); u.send(bytes((lec + 7) // 8))        # 4. reconciliation traffic
        L = max(0, math.floor((nk - nt) * (1 - h2(Qup)) - lec - 2 * math.log2(1 / a.eps)))
        print(json.dumps(dict(role="sender", aborted=False, Qhat=Qhat, key=L, wall_s=round(time.time()-t0, 2), frames=u.frames_tx, timeouts=u.timeouts, bits=u.bits)))
    else:                                                     # ---- Receiver
        u.send(np.packbits(rb.astype(np.uint8)).tobytes())                           # 1. receiver bases
        keep = np.unpackbits(np.frombuffer(u.recv(), np.uint8))[:a.n].astype(bool)  # 2. sifting mask
        nk = int(keep.sum()); idx = np.random.default_rng(a.seed + 9).permutation(nk); nt = int(a.test_frac * nk)
        kr = res[keep]; ks_t = np.unpackbits(np.frombuffer(u.recv(), np.uint8))[:nt]  # 3. sender test bits
        Qhat = float(np.mean(ks_t != kr[idx[:nt]])); Qup = Qhat + math.sqrt(math.log(1 / a.eps) / (2 * nt))
        v = dict(Qhat=Qhat, Qup=Qup, abort=Qup > 0.11, Qtrue_est=Qhat); u.send(json.dumps(v).encode())     # 4. verdict
        if v["abort"]: print(json.dumps(dict(role="receiver", aborted=True, Qhat=Qhat, wall_s=round(time.time()-t0, 2), frames_lost=u.frames_lost, frames_tx=u.frames_tx))); return
        u.recv()                                                                      # 5. reconciliation traffic
        L = max(0, math.floor((nk - nt) * (1 - h2(Qup)) - int(1.16 * h2(Qhat) * (nk - nt)) - 2 * math.log2(1 / a.eps)))
        print(json.dumps(dict(role="receiver", aborted=False, Qhat=Qhat, key=L, wall_s=round(time.time()-t0, 2), frames_lost=u.frames_lost, frames_tx=u.frames_tx)))

if __name__ == "__main__":
    main()
