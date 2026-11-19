#!/usr/bin/env python3
"""H1.94E SW -- fresh gain sweep, automated, with the order fixed in advance by a seed.
Sender: for every item of the schedule starts the QKD transmitter at the item's gain (or stays silent for a noise-only item).
Receiver: captures (13 s), analyses the capture with the unchanged lab analyser (MMSE and ZF), records SHA-256 of the raw files,
then deletes them unless --keep. A UDP doorbell on the LAN carries only start/done tokens. Antennas stay in the forward geometry:
Sender TX1/TX2, Receiver RX1/RX2. Start the Receiver first.
  Receiver: python3 H194E_SW_SWEEP.py --role receiver --peer SENDER_IP:6002 --listen 6001 --lib . --tag W1
  Sender  : python3 H194E_SW_SWEEP.py --role sender   --peer RECEIVER_IP:6001 --listen 6002 --lib . --tag W1
Same arguments (--gains, --reps, --order-seed, --noise-every) on both PCs. Results: sweep_W1/manifest.json (Receiver)."""
import argparse, hashlib, json, os, random, subprocess, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import H194E_R2_RADIO_BB84 as R2

def schedule(seed, gains, reps, noise_every):
    items = [(g, r) for g in gains for r in range(reps)]; random.Random(seed).shuffle(items)
    out = [("OFF", 0)]
    for i, it in enumerate(items):
        out.append(it)
        if (i + 1) % noise_every == 0: out.append(("OFF", i + 1))
    if out[-1][0] != "OFF": out.append(("OFF", len(items) + 1))
    return out

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""): h.update(b)
    return h.hexdigest()

def noise_stats(p0, p1, skip=200_000, n=4_000_000):
    x = [np.fromfile(p, np.complex64, count=skip + n)[skip:].astype(np.complex128) for p in (p0, p1)]
    c = np.mean(x[0] * np.conj(x[1])); p = [np.mean(np.abs(v) ** 2) for v in x]
    return dict(rms0=float(np.sqrt(p[0])), rms1=float(np.sqrt(p[1])), rho=float(abs(c) / np.sqrt(p[0] * p[1])), phase_deg=float(np.degrees(np.angle(c))))

def capture(a, radio, tag, state):
    if a.mode == "sim":
        if state == "ON": return radio.capture(tag)
        rng = np.random.default_rng(abs(hash(tag)) % 2**32); p = []
        for i in range(2):
            fn = str(Path(a.simdir) / f"{tag}_RX{i}.c64"); (0.002 * (rng.standard_normal(4_400_000) + 1j * rng.standard_normal(4_400_000))).astype(np.complex64).tofile(fn); p.append(fn)
        return p
    subprocess.run([sys.executable, a.capture_script, "--state", state, "--tag", tag, "--seconds", str(a.cap_seconds)], capture_output=True, text=True)
    p = [f"H194E_V18Z34_{tag}_{state}_RX{i}.c64" for i in range(2)]
    return p if all(os.path.exists(x) for x in p) else None

def analyse(a, p, out):
    res = {}
    for det in ("MMSE", "ZF"):
        r = subprocess.run([sys.executable, str(Path(a.lib).expanduser() / "H194E_V18Z38_QKD_ANALYZE.py"), "--rx0", p[0], "--rx1", p[1], "--detector", det, "--out", str(out) + "_" + det],
                           capture_output=True, text=True)
        Path(str(out) + f"_{det}.txt").write_text(r.stdout + r.stderr)
        j = Path(str(out) + f"_{det}_qkd.json")
        res[det] = json.loads(j.read_text()) if j.exists() else {"error": "analyser failed"}
    return res

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--role", choices=["sender", "receiver"], required=True)
    ap.add_argument("--lib", default="."); ap.add_argument("--peer", required=True); ap.add_argument("--listen", type=int, required=True)
    ap.add_argument("--mode", choices=["lab", "sim"], default="lab"); ap.add_argument("--simdir", default="/tmp/swsim")
    ap.add_argument("--gains", default="6,8,10,12,14,16"); ap.add_argument("--reps", type=int, default=3); ap.add_argument("--order-seed", type=int, default=20261109)
    ap.add_argument("--noise-every", type=int, default=6); ap.add_argument("--tag", default="W1"); ap.add_argument("--keep", action="store_true")
    ap.add_argument("--frames", type=int, default=256); ap.add_argument("--seed", type=int, default=20261030); ap.add_argument("--cap-seconds", type=float, default=13)
    ap.add_argument("--capture-script", default="H194E_V18Z34_CAPTURE.py"); ap.add_argument("--settle", type=float, default=5.0)
    ap.add_argument("--sim-snr-f", type=float, default=12); ap.add_argument("--sim-snr-r", type=float, default=12); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    a.gain_q = 14.0; a.gain_f = 14.0; a.gain_r = 14.0; a.yes = True; a.part_bytes = 4700
    sched = schedule(a.order_seed, [float(g) for g in a.gains.split(",")], a.reps, a.noise_every)
    print(f"{len(sched)} items:", " ".join(("OFF" if g == "OFF" else f"{g:g}") for g, _ in sched))
    if a.dry_run: return
    sys.path.insert(0, str(Path(a.lib).expanduser())); import H194E_Z38_COMMON as C
    ph, pp = a.peer.split(":"); bell = R2.Bell(a.listen, (ph, int(pp))); radio = (R2.SimRadio if a.mode == "sim" else R2.LabRadio)(a, C)
    out = Path(f"sweep_{a.tag}"); out.mkdir(exist_ok=True); manifest = []
    bell.send(dict(cmd="hello")); assert bell.recv()["cmd"] == "hello"; print("peer connected", flush=True)
    try:
        for k, (g, rep) in enumerate(sched):
            tag = f"SW{a.tag}{k:02d}"
            if a.role == "sender":
                if g != "OFF": a.gain_q = float(g); radio.tx_start("quantum", None, 0)
                bell.send(dict(cmd="cap", k=k, g=g)); r = bell.recv(); assert r["cmd"] == "done", r
                radio.tx_stop(); print(f"  item {k + 1}/{len(sched)} gain {g} done", flush=True)
            else:
                m = bell.recv(); assert m["cmd"] == "cap" and m["k"] == k, m
                state = "OFF" if g == "OFF" else "ON"; p = capture(a, radio, tag, state); rec = dict(k=k, tag=tag, gain=g, state=state, t=time.strftime("%Y-%m-%d %H:%M:%S"))
                if p:
                    rec["sha256"] = [sha(x) for x in p]
                    if state == "OFF": rec["noise"] = noise_stats(*p)
                    else: rec["analysis"] = analyse(a, p, out / tag)
                    if not a.keep:
                        for x in p: os.path.exists(x) and os.remove(x)
                else: rec["error"] = "capture failed"
                manifest.append(rec); (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
                s = rec.get("analysis", {}).get("MMSE", {}); print(f"  item {k + 1}/{len(sched)} gain {g} {state}: " + (f"MMSE QBER {100 * s.get('qber', float('nan')):.2f}% SINR {s.get('sinr_mean_db', float('nan')):.1f} dB" if s else json.dumps(rec.get("noise", rec.get("error")))), flush=True)
                bell.send(dict(cmd="done", k=k))
    finally: radio.tx_stop()
    print("sweep complete; results in", out)

if __name__ == "__main__":
    main()
