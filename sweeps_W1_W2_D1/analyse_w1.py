import json, re, math, numpy as np
from pathlib import Path
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
D = Path("sweep_W1"); man = json.load(open(D / "manifest.json"))
def wilson(e, n, z=1.96):
    p = e / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return c - h, c + h
rows = []; excl = []
for r in man:
    if r["state"] != "ON": continue
    txt = (D / f"{r['tag']}_MMSE.txt").read_text(); m = re.search(r"Frames synchronised:\s*(\d+)", txt); nfr = int(m.group(1)) if m else 0
    a = r.get("analysis", {}); M, Z = a.get("MMSE", {}), a.get("ZF", {})
    if nfr < 200 or "qber" not in M or "qber" not in Z: excl.append((r["tag"], r["gain"], nfr)); continue
    n = M["sifted"]; row = dict(tag=r["tag"], gain=r["gain"], sinr=M["sinr_mean_db"], sa=M["sinr_a_db"], sb=M["sinr_b_db"], cond=M["cond"], n=n,
        qm=M["qber"], qz=Z["qber"], key_m=0 if M["abort"] else M["final_bits"], key_z=0 if Z["abort"] else Z["final_bits"], abort_m=M["abort"], abort_z=Z["abort"], frames=nfr)
    row["em"] = round(row["qm"] * n); row["ez"] = round(row["qz"] * n); row["cim"] = wilson(row["em"], n); row["ciz"] = wilson(row["ez"], n); rows.append(row)
rows.sort(key=lambda x: (-x["gain"], x["tag"]))
print("excluded:", excl)
print(f"{'gain':>4} {'tag':>7} {'SINR':>5} {'MMSE%':>6} {'95% CI':>13} {'ZF%':>6} {'ZF/MMSE':>7} {'keyM':>6} {'keyZ':>6}")
for x in rows: print(f"{x['gain']:4.0f} {x['tag']:>7} {x['sinr']:5.1f} {100*x['qm']:6.2f} [{100*x['cim'][0]:5.2f},{100*x['cim'][1]:5.2f}] {100*x['qz']:6.2f} {x['qz']/x['qm']:7.2f} {x['key_m']:6d} {x['key_z']:6d}")
dec = [x for x in rows]; km = sum(x["key_m"] > 0 for x in dec); kz = sum(x["key_z"] > 0 for x in dec)
ratio = np.array([x["qz"] / x["qm"] for x in dec if x["qm"] > 0]); print(f"\ndecodable {len(dec)} of 18; key MMSE {km}, ZF {kz}")
print(f"ZF/MMSE ratio: median {np.median(ratio):.2f}, range {ratio.min():.2f}-{ratio.max():.2f}; ratio>1 in {int((ratio>1).sum())}/{len(ratio)} ({100*(ratio>1).mean():.0f}%)")
rng = np.random.default_rng(1); bs = [np.median(rng.choice(ratio, len(ratio))) for _ in range(5000)]; print("bootstrap 95% CI of median ratio:", np.round(np.percentile(bs, [2.5, 97.5]), 2))
print("per gain mean MMSE QBER %, n, spread:")
for g in sorted({x["gain"] for x in dec}, reverse=True):
    q = [100 * x["qm"] for x in dec if x["gain"] == g]; print(f"  {g:4.0f} dB: mean {np.mean(q):5.2f}  n={len(q)}  range {min(q):.2f}-{max(q):.2f}  sinr {np.mean([x['sinr'] for x in dec if x['gain']==g]):.1f}")
nz = [r for r in man if r["state"] == "OFF"]
print("noise-only: rho", [round(r["noise"]["rho"], 3) for r in nz], "phase", [round(r["noise"]["phase_deg"], 1) for r in nz], "rms0", [round(1e3 * r["noise"]["rms0"], 2) for r in nz], "rms1", [round(1e3 * r["noise"]["rms1"], 2) for r in nz])
print("rho change first-last", round(nz[-1]["noise"]["rho"] - nz[0]["noise"]["rho"], 3))
json.dump(rows, open("w1_table.json", "w"), indent=1)
fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=200)
for k, c, lab, mk in (("m", "#1f4e8c", "MMSE", "o"), ("z", "#c0392b", "ZF", "s")):
    s = np.array([x["sinr"] for x in dec]); q = np.array([100 * x["q" + k] for x in dec])
    lo = np.array([100 * x["ci" + k][0] for x in dec]); hi = np.array([100 * x["ci" + k][1] for x in dec])
    ax.errorbar(s, q, yerr=[q - lo, hi - q], fmt=mk, ms=4, color=c, mfc=c if k == "m" else "none", lw=0.8, label=lab)
ax.axhline(6.55, color="#7f8c8d", ls=":", lw=1); ax.text(10.9, 6.85, "key limit 6.55%", fontsize=6.5, color="#7f8c8d", ha="right")
ax.set_yscale("log"); ax.set_xlabel("measured post-MMSE SINR (dB)"); ax.set_ylabel("QBER (%)"); ax.grid(alpha=.25, which="both"); ax.legend(frameon=False, fontsize=7)
fig.tight_layout(); fig.savefig("w1_qber_sinr.png")
