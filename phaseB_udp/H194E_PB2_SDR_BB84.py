#!/usr/bin/env python3
"""Phase B2: BB84 whose quantum layer is the REAL SDR 2x2 MIMO capture and whose public channel is real UDP.
Receiver: decodes RX0/RX1 captures, measures every decoded qubit in its own random basis, then runs the Phase B
exchange with the Sender (bases -> mask -> test bits -> verdict -> reconciliation traffic).
Sender: regenerates its own bases/bits from the TX seed for the frame indices the Receiver reports.
Needs H194E_PB_UDP_BB84.py in the same folder; --lib = folder with H194E_Z38_COMMON.py (Receiver: also the analyser files)."""
import argparse, json, math, os, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from H194E_PB_UDP_BB84 import Udp, h2

def rx_measure(A, Z, C, rx0, rx1, rseed):
    """Front end copied from the analyser: returns sorted frame indices, Receiver bases and measured bits (per qubit)."""
    x = [np.fromfile(p, dtype=np.complex64) for p in (rx0, rx1)]
    n = min(len(x[0]), len(x[1])); x = [v[A.SKIP:n] for v in x]
    cfo, _ = Z.estimate_cfo(x); ys = [Z.boxcar(Z.derotate(v, Z.F0 + cfo)) for v in x]
    metric = sum(np.abs(Z.pilot_correlation(y, Z.PA)) ** 2 for y in ys)
    peaks, med, top = Z.pick_peaks(metric)
    yks = [(n0, Z.frame_symbols(ys, n0)) for n0 in peaks]; yks = [(n0, k) for n0, k in yks if k is not None]
    if not yks: sys.exit("No frames found (check TX/RX, gains, file names).")
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
    if hasattr(A, "_fit_chat"):                                  # lab analyser: pooled full receive-noise covariance
        A.CHAT = None if os.environ.get("H194E_DIAGR") == "1" else A._fit_chat(yks, om)
    seen = {}
    for n0, yk in yks:
        est = A.decode_frame(yk, om, "MMSE")[2]; i = A.read_idx(est)
        if i is not None and i not in seen: seen[i] = est
    fl = sorted(seen); rb, rbit = [], []
    for i in fl:
        bb = np.random.RandomState([rseed, i]).randint(0, 2, C.N_Q).astype(np.uint8)
        rb.append(bb); rbit.append(A.measure(seen[i], bb))
    return np.array(fl, np.uint8), np.concatenate(rb), np.concatenate(rbit)

def sender_data(C, seed, fl):
    sb, sx = [], []
    for i in fl:
        b, v = C.sender_qubits(seed, int(i)); sx.append(b); sb.append(v)
    return np.concatenate(sb), np.concatenate(sx)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--role", choices=["sender", "receiver"], required=True)
    ap.add_argument("--lib", required=True); ap.add_argument("--listen", type=int, required=True); ap.add_argument("--peer", required=True)
    ap.add_argument("--rx0"); ap.add_argument("--rx1"); ap.add_argument("--seed", type=int, default=20261030)
    ap.add_argument("--receiver-seed", type=int, default=777); ap.add_argument("--p-loss", type=float, default=0.0)
    ap.add_argument("--t-frame", type=float, default=0.048); ap.add_argument("--eps", type=float, default=1e-6)
    ap.add_argument("--test-frac", type=float, default=0.1); ap.add_argument("--out", default=None); a = ap.parse_args()
    sys.path.insert(0, str(Path(a.lib).expanduser())); import H194E_Z38_COMMON as C
    ph, pp = a.peer.split(":"); me = a.role == "sender"
    u = Udp(a.listen, (ph, int(pp)), a.t_frame, a.p_loss, 1 + (0 if me else 1), 1.0); t0 = time.time()
    if me:
        msg = u.recv(); nf = len(msg) // 35; fl = np.frombuffer(msg[:nf], np.uint8)
        bases_r = np.unpackbits(np.frombuffer(msg[nf:], np.uint8))[:nf * C.N_Q]
        sb, sx = sender_data(C, a.seed, fl); n = len(sb)
        keep = bases_r == sx; u.send(np.packbits(keep.astype(np.uint8)).tobytes())
        nk = int(keep.sum()); idx = np.random.default_rng(10).permutation(nk); nt = int(a.test_frac * nk)
        u.send(np.packbits(sb[keep][idx[:nt]]).tobytes())
        v = json.loads(u.recv().decode())
        if v["abort"]: r = dict(role="sender", aborted=True, Qhat=v["Qhat"], qubits=n, wall_s=round(time.time()-t0, 2), frames=u.frames_tx, timeouts=u.timeouts)
        else:
            lec = int(1.16 * h2(v["Qtrue_est"]) * (nk - nt)); u.send(bytes((lec + 7) // 8))
            L = max(0, math.floor((nk - nt) * (1 - h2(v["Qup"])) - lec - 2 * math.log2(1 / a.eps)))
            r = dict(role="sender", aborted=False, Qhat=v["Qhat"], key=L, qubits=n, sifted=nk, wall_s=round(time.time()-t0, 2), frames=u.frames_tx, timeouts=u.timeouts)
    else:
        sys.path.insert(0, str(Path(a.lib).expanduser()))
        import H194E_V18Z37_MIMO_ANALYZE as Z, H194E_V18Z38_QKD_ANALYZE as A
        fl, rb, rbit = rx_measure(A, Z, C, a.rx0, a.rx1, a.receiver_seed); n = len(rb)
        print(json.dumps(dict(role="receiver", decoded_frames=len(fl), qubits=n)), flush=True)
        u.send(fl.tobytes() + np.packbits(rb).tobytes())
        keep = np.unpackbits(np.frombuffer(u.recv(), np.uint8))[:n].astype(bool)
        nk = int(keep.sum()); idx = np.random.default_rng(10).permutation(nk); nt = int(a.test_frac * nk)
        kr = rbit[keep]; ks_t = np.unpackbits(np.frombuffer(u.recv(), np.uint8))[:nt]
        Qhat = float(np.mean(ks_t != kr[idx[:nt]])); Qup = Qhat + math.sqrt(math.log(1 / a.eps) / (2 * nt))
        sb, sx = sender_data(C, a.seed, fl); qfull = float(np.mean(sb[keep] != kr))     # reference only (not used by the protocol)
        v = dict(Qhat=Qhat, Qup=Qup, abort=Qup > 0.11, Qtrue_est=Qhat); u.send(json.dumps(v).encode())
        r = dict(role="receiver", aborted=v["abort"], Qhat=Qhat, Q_all_sifted_reference=round(qfull, 5), qubits=n, sifted=nk, wall_s=round(time.time()-t0, 2), frames_lost=u.frames_lost, frames_tx=u.frames_tx)
        if not v["abort"]:
            u.recv(); r["key"] = max(0, math.floor((nk - nt) * (1 - h2(Qup)) - int(1.16 * h2(Qhat) * (nk - nt)) - 2 * math.log2(1 / a.eps)))
            r["wall_s"] = round(time.time()-t0, 2)
    print(json.dumps(r))
    if a.out: Path(a.out).write_text(json.dumps(r))

if __name__ == "__main__":
    main()
