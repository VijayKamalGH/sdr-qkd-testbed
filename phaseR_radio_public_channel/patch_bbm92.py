p = "H194E_R2_RADIO_BB84.py"; s = open(p).read()
assert "bbm92" not in s
R = [
 ('ap.add_argument("--settle", type=float, default=5.0);', 'ap.add_argument("--protocol", choices=["bb84", "bbm92"], default="bb84"); ap.add_argument("--settle", type=float, default=5.0);'),
 ('run.exchange_tx("mask+test", "F", np.packbits(keep.astype(np.uint8)).tobytes() +', 'run.exchange_tx("mask+test", "F", np.packbits((sx if a.protocol == "bbm92" else keep).astype(np.uint8)).tobytes() +'),
 ('keep = np.unpackbits(np.frombuffer(msg[:ml], np.uint8))[:n].astype(bool)', 'keep = np.unpackbits(np.frombuffer(msg[:ml], np.uint8))[:n].astype(bool)\n            if a.protocol == "bbm92": keep = keep.astype(np.uint8) == rb'),
 ('r.update(wall_s=round(time.time() - t0, 1),', 'r.update(protocol=a.protocol, wall_s=round(time.time() - t0, 1),'),
]
for x, y in R:
    assert s.count(x) == 1, x
    s = s.replace(x, y)
open(p, "w").write(s); print("patched")
