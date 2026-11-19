import json, math, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
def wilson(e, n, z=1.96):
    p = e / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return c - h, c + h
def load(path):
    man = json.load(open(path)); rows = []; excl = []
    for r in man:
        if r["state"] != "ON": continue
        a = r.get("analysis", {}); M, Z = a.get("MMSE", {}), a.get("ZF", {})
        if "qber" not in M or "qber" not in Z: excl.append((r["tag"], r["gain"])); continue
        n = M["sifted"]; row = dict(tag=r["tag"], gain=r["gain"], sinr=M["sinr_mean_db"], n=n, qm=M["qber"], qz=Z["qber"], frames=M["frames"],
            key_m=0 if M["abort"] else M["final_bits"], key_z=0 if Z["abort"] else Z["final_bits"])
        row["cim"] = wilson(round(row["qm"] * n), n); row["ciz"] = wilson(round(row["qz"] * n), Z["sifted"]); rows.append(row)
    nz = [r["noise"] for r in man if r["state"] == "OFF"]; return rows, excl, nz
R = {}
for name, p in (("W1", "sweep_W1/manifest.json"), ("W2", "w2/manifest.json")):
    rows, excl, nz = load(p); rows.sort(key=lambda x: (-x["gain"], x["tag"])); R[name] = rows
    ratio = np.array([x["qz"] / x["qm"] for x in rows]); print(f"== {name}: decodable {len(rows)} of 18, excluded {excl}")
    print(f"  key MMSE {sum(x['key_m']>0 for x in rows)}, ZF {sum(x['key_z']>0 for x in rows)}; ZF/MMSE median {np.median(ratio):.2f} range {ratio.min():.2f}-{ratio.max():.2f}; >1 in {int((ratio>1).sum())}/{len(ratio)}")
    for g in sorted({x["gain"] for x in rows}, reverse=True):
        q = [100 * x["qm"] for x in rows if x["gain"] == g]; s = [x["sinr"] for x in rows if x["gain"] == g]; kz = [x["key_z"] for x in rows if x["gain"] == g]; km = [x["key_m"] for x in rows if x["gain"] == g]
        print(f"  {g:4.0f} dB n={len(q)} MMSE {np.mean(q):5.2f}% [{min(q):.2f}-{max(q):.2f}] SINR {np.mean(s):.1f}  keys MMSE {km} ZF {kz}")
    print("  noise-only rho", [round(z["rho"], 3) for z in nz], "phase", [round(z["phase_deg"], 1) for z in nz], "change", round(nz[-1]["rho"] - nz[0]["rho"], 3))
fig, ax = plt.subplots(figsize=(5.4, 3.7), dpi=200)
for name, mk, c in (("W1", "o", "#1f4e8c"), ("W2", "^", "#2e8b57")):
    for det, key, ci, fill in (("MMSE", "qm", "cim", True), ("ZF", "qz", "ciz", False)):
        s = np.array([x["sinr"] for x in R[name]]); q = 100 * np.array([x[key] for x in R[name]]); lo = 100 * np.array([x[ci][0] for x in R[name]]); hi = 100 * np.array([x[ci][1] for x in R[name]])
        col = c if fill else "#c0392b"
        ax.errorbar(s, q, yerr=[np.maximum(q - lo, 0), np.maximum(hi - q, 0)], fmt=mk, ms=4, color=col, mfc=col if fill else "none", lw=0.7, label=f"{det} {name}")
ax.axhline(6.55, color="#7f8c8d", ls=":", lw=1); ax.set_yscale("log"); ax.set_xlabel("measured post-MMSE SINR (dB)"); ax.set_ylabel("QBER (%)"); ax.grid(alpha=.25, which="both"); ax.legend(frameon=False, fontsize=6, ncol=2)
fig.tight_layout(); fig.savefig("w1w2_qber_sinr.png")
json.dump(R, open("w1w2_table.json", "w"), indent=1)
