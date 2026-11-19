import sys, hashlib
p = sys.argv[1]; s = open(p).read()
def rep(a, b):
    global s
    assert s.count(a) == 1, ("anchor not found / not unique", a[:60]); s = s.replace(a, b)
# 1. accumulators
rep("    E_f = 0; E_fm = 0.0;", "    E_zf = 0; E_zfm = 0.0; E_zfn = 0\n    E_f = 0; E_fm = 0.0;")
# 2. per-frame ZF block, right after the full-R model Monte Carlo accumulation
rep("        E_fm += efm / a.mc\n",
"""        E_fm += efm / a.mc
        # ---- zero-forcing receiver on the same frame: z = H^-1 y, unbiased; blind frame-constant phase correction
        Hi = np.linalg.pinv(H); estz = Hi @ d
        thz = 0.5 * np.angle(np.sum(estz[:, C.N_IDX:] ** 2)); estz = estz * np.exp(-1j * thz)
        E_zf += ((meas(estz, bbas) != abit) & sF).sum(); E_zfn += sF.sum()
        Sz = Hi @ Rf @ Hi.conj().T; Sz = (Sz + Sz.conj().T) / 2; Lz = np.linalg.cholesky(Sz + 1e-15 * np.eye(2)); ezm = 0.0
        for _ in range(a.mc):
            wz = Lz @ (rng.standard_normal((2, C.N_Q)) + 1j * rng.standard_normal((2, C.N_Q))) / np.sqrt(2)
            ezm += ((meas(S + wz, bbas) != abit) & sF).sum()
        E_zfm += ezm / a.mc
""")
# 3. results
rep("               qber_fullR_measured=float(E_f / N_sift),", "               qber_zf_measured=float(E_zf / max(E_zfn, 1)), qber_zf_model=float(E_zfm / max(E_zfn, 1)),\n               qber_fullR_measured=float(E_f / N_sift),")
rep("""    print("QBER vs position in frame (\"""", """    print(f"--- zero-forcing receiver (H^-1, same frame, phase-corrected) ---")
    print(f"QBER ZF measured {100*res['qber_zf_measured']:5.2f} %   ZF model (full-R) {100*res['qber_zf_model']:5.2f} %   measured/model {res['qber_zf_measured']/max(res['qber_zf_model'],1e-9):.2f}")
    print("QBER vs position in frame (\"""")
open(p, "w").write(s); print("patched", p, hashlib.md5(s.encode()).hexdigest())
