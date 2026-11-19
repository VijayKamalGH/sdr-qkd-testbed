#!/usr/bin/env python3
"""H1.94E V18-Z38 full-covariance check (read-only: does NOT modify the analyzer).

Compares, per capture, the measured post-MMSE statistics with the exact model
    z = (I-P) s + w,  w ~ CN(0, P - P^2),  P = (I + H^H N^-1 H)^-1,
using the receiver's own (H, N) per frame and Sender's known transmitted qubits.
The analyzer outputs the UNBIASED MMSE estimate  est = D^-1 z,  D = diag(I-P),
so both the unbiased and the raw variants are simulated.

Usage:  python3 H194E_V18Z38_COV_CHECK.py --rx0 A_RX0.c64 --rx1 A_RX1.c64 --tag N12B
Needs the analyzer file H194E_V18Z38_QKD_ANALYZE.py in the same folder.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import H194E_V18Z38_QKD_ANALYZE as A
C, Z = A.C, A.Z

def frames_from_capture(rx0, rx1):
    """Same front end as the analyzer main(): CFO, sync, residual CFO, per-frame decode."""
    x = [np.fromfile(p, dtype=np.complex64) for p in (rx0, rx1)]
    n = min(len(x[0]), len(x[1])); x = [v[A.SKIP:n] for v in x]
    cfo, _ = Z.estimate_cfo(x)
    ys = [Z.boxcar(Z.derotate(v, Z.F0 + cfo)) for v in x]
    metric = sum(np.abs(Z.pilot_correlation(y, Z.PA)) ** 2 for y in ys)
    peaks, _, _ = Z.pick_peaks(metric)
    yks = [(n0, Z.frame_symbols(ys, n0)) for n0 in peaks]; yks = [(n0, k) for n0, k in yks if k is not None]
    if not yks: sys.exit("No frames found.")
    om = float(np.median([Z.pilot_om(k) for _, k in yks]))
    hp = [(n0, np.mean(k[:, :C.N_PILOT] * Z.PA, axis=1)) for n0, k in yks]
    zacc, npair = 0j, 0
    for (na, ha), (nb, hb) in zip(hp[:-1], hp[1:]):
        if abs((nb - na) - Z.PERIOD) <= 600: zacc += np.sum(np.conj(ha) * hb); npair += 1
    if npair >= 10: om = float(np.angle(zacc) / C.N_SYM)
    if len(yks) > 1:
        pos = np.array([n0 for n0, _ in yks]); keep = []
        for p in pos:
            d = np.abs(pos - p); m = np.rint(d / Z.PERIOD)
            keep.append(bool((((m >= 1) & (m <= 4)) & (np.abs(d - m * Z.PERIOD) <= 600)).any()))
        yks = [t for t, k in zip(yks, keep) if k]
    seen = {}
    for n0, yk in yks:
        r = A.decode_frame(yk, om, "MMSE")          # works for 3- or 4-value return
        H, noise, est = r[0], r[1], r[2]
        i = A.read_idx(est)
        if i is None or i in seen: continue
        kk = np.arange(C.N_SYM)
        ykc = yk * np.exp(-1j * om * kk)[None, :]
        seen[i] = (H, noise, ykc[:, C.I0:C.Q1][:, C.N_IDX:], ykc[:, C.Q1 + 2:])
    return seen, cfo

def meas(z, basis):
    z1, z2 = z[0].real, z[1].real
    zb = (np.abs(z2) > np.abs(z1)).astype(np.uint8); xb = (z1 * z2 < 0).astype(np.uint8)
    return np.where(basis == 0, zb, xb).astype(np.uint8)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rx0", type=Path, required=True); ap.add_argument("--rx1", type=Path, required=True)
    ap.add_argument("--tag", default="cap"); ap.add_argument("--seed", type=int, default=20261030)
    ap.add_argument("--receiver-seed", type=int, default=777); ap.add_argument("--mc", type=int, default=20)
    ap.add_argument("--nbins", type=int, default=8); ap.add_argument("--phase-win", type=int, default=32)
    a = ap.parse_args()
    seen, cfo = frames_from_capture(a.rx0, a.rx1)
    rng = np.random.default_rng(1)
    nb = a.nbins; edges = np.linspace(0, C.N_Q, nb + 1).astype(int)
    e_meas = np.zeros(nb); e_cnt = np.zeros(nb)
    # accumulators
    maha, nmaha = 0.0, 0
    rv = np.zeros((2, 2)); rn = 0          # empirical real/imag variance per stream, normalised by prediction
    cross_e, cross_p = 0.0, 0.0
    pseudo = 0.0
    E_meas = 0; N_sift = 0
    E_unb = 0.0; E_raw = 0.0; Vfr = 0.0
    fr_err, fr_n, fr_pred = [], [], []
    logP = []; gain_dev = []
    ph_dev = [[], []]; mag_dev = [[], []]; ph_noise = [[], []]; offd = []
    rres = np.zeros((2, 2)); rres_n = 0; slope = [[], []]
    Ng = np.zeros((2, 2), complex); Nd = np.zeros((2, 2), complex); ng_n = 0; nd_n = 0
    _Ng = sum(gd @ gd.conj().T for (_, _, _, gd) in seen.values()); _dg = np.sqrt(np.real(np.diag(_Ng)))
    Chat = _Ng / np.outer(_dg, _dg)                       # pooled noise correlation matrix (unit diagonal), from the guard slots
    E_f = 0; E_fm = 0.0; maha_f = 0.0; rvf = np.zeros((2, 2)); E_pt = 0; E_pf = 0; thf = []; thstd = []; rvp = np.zeros((2, 2)); mah_p = 0.0; phAB = [[], []]
    for i, (H, nz, d, gd) in sorted(seen.items()):
        abas, abit = C.sender_qubits(a.seed, i)
        bbas = np.random.RandomState([a.receiver_seed, i]).randint(0, 2, C.N_Q).astype(np.uint8)
        S = np.array([C.VEC[(int(b), int(v))] for b, v in zip(abas, abit)]).T       # 2 x 272 real
        N = np.diag(nz); Ninv = np.diag(1.0 / nz)
        P = np.linalg.inv(np.eye(2) + H.conj().T @ Ninv @ H); P = (P + P.conj().T) / 2
        IP = np.eye(2) - P; D = np.real(np.diag(IP)); Cw = P - P @ P; Cw = (Cw + Cw.conj().T) / 2
        W = H.conj().T @ np.linalg.inv(H @ H.conj().T + N)
        zraw = W @ d; est = zraw / D[:, None]
        # ---- covariance check on the unbiased output
        mean = (IP @ S) / D[:, None]
        Cu = Cw / np.outer(D, D)                              # complex covariance of est
        e = est - mean
        Ci = np.linalg.inv(Cu + 1e-18 * np.eye(2))
        q = np.real(np.einsum('kn,kl,ln->n', e.conj(), Ci, e))     # expect mean 2 (complex dim 2)
        maha += q.sum(); nmaha += q.size
        for k in range(2):
            rv[k, 0] += np.sum(e[k].real ** 2) / (0.5 * Cu[k, k].real); rv[k, 1] += np.sum(e[k].imag ** 2) / (0.5 * Cu[k, k].real)
        rn += e.shape[1]
        cross_e += np.sum(e[0].real * e[1].real); cross_p += 0.5 * Cu[0, 1].real * e.shape[1]
        pseudo += np.mean(np.abs(np.sum(e[0] * e[0]) / e.shape[1]) / Cu[0, 0].real)
        # ---- per-frame gain/phase check: LS fit est ~ G s, compare with the model map M = D^-1 (I-P)
        SS = S @ S.T
        if np.linalg.cond(SS) < 1e3:
            Gm = (est @ S.T) @ np.linalg.inv(SS); Mm = IP / D[:, None]
            Rm = Gm @ np.linalg.inv(Mm); SSi = np.linalg.inv(SS)
            for k in range(2):
                ph_dev[k].append(np.angle(Rm[k, k])); mag_dev[k].append(abs(Rm[k, k]) - 1)
                ph_noise[k].append(np.sqrt(0.5 * Cu[k, k].real * SSi[k, k]) / abs(Mm[k, k]))
            offd.append(abs(Rm[0, 1]) + abs(Rm[1, 0]))
            # residual after removing the per-frame 2x2 map: should match the model covariance if only H errors remain
            rr = est - Gm @ S
            for k in range(2):
                rres[k, 0] += np.sum(rr[k].real ** 2) / (0.5 * Cu[k, k].real); rres[k, 1] += np.sum(rr[k].imag ** 2) / (0.5 * Cu[k, k].real)
            rres_n += rr.shape[1]
            nhat = np.linalg.solve(W, D[:, None] * rr)          # input-referred noise during the data slots (after removing the H-error part)
            Nd += nhat @ nhat.conj().T; nd_n += nhat.shape[1]
            Ng += gd @ gd.conj().T; ng_n += gd.shape[1]
            # in-frame phase slope: LS map on the first and second half of the qubit block
            h = C.N_Q // 2; ok = True; ph = []
            for sl in (slice(0, h), slice(h, C.N_Q)):
                Sh = S[:, sl]; SSh = Sh @ Sh.T
                if np.linalg.cond(SSh) > 1e3: ok = False; break
                Gh = (est[:, sl] @ Sh.T) @ np.linalg.inv(SSh); Rh = Gh @ np.linalg.inv(Mm)
                ph.append([np.angle(Rh[0, 0]), np.angle(Rh[1, 1])])
            if ok:
                for k in range(2):
                    slope[k].append(np.angle(np.exp(1j * (ph[1][k] - ph[0][k]))) / h * (C.FS / C.SPS) / (2 * np.pi))   # Hz
        # ---- same frame, but with the FULL noise covariance R = sqrt(N) Chat sqrt(N) in the equaliser and in the model
        sq = np.sqrt(nz); Rf = sq[:, None] * Chat * sq[None, :]
        Pf = np.linalg.inv(np.eye(2) + H.conj().T @ np.linalg.inv(Rf) @ H); Pf = (Pf + Pf.conj().T) / 2
        IPf = np.eye(2) - Pf; Df = np.real(np.diag(IPf)); Cwf = Pf - Pf @ Pf; Cwf = (Cwf + Cwf.conj().T) / 2
        Wf = H.conj().T @ np.linalg.inv(H @ H.conj().T + Rf); estf = (Wf @ d) / Df[:, None]
        Cuf = Cwf / np.outer(Df, Df); ef = estf - (IPf @ S) / Df[:, None]
        qf = np.real(np.einsum('kn,kl,ln->n', ef.conj(), np.linalg.inv(Cuf + 1e-18 * np.eye(2)), ef)); maha_f += qf.sum()
        for k in range(2):
            rvf[k, 0] += np.sum(ef[k].real ** 2) / (0.5 * Cuf[k, k].real); rvf[k, 1] += np.sum(ef[k].imag ** 2) / (0.5 * Cuf[k, k].real)
        # ---- blind common-phase tracking: s1^2+s2^2 = 1 for all four states, so angle(sum est_k^2)/2 is the common phase error
        u = estf[0] ** 2 + estf[1] ** 2
        def _smooth(v, L):
            k = np.ones(L); return np.convolve(v, k, "same") / np.convolve(np.ones(len(v)), k, "same")
        th_t = 0.5 * np.angle(_smooth(u, a.phase_win)); th_f = np.full(len(u), 0.5 * np.angle(np.sum(u)))
        est_t = estf * np.exp(-1j * th_t)[None, :]; est_f = estf * np.exp(-1j * th_f)[None, :]
        sF = abas == bbas
        E_pt += ((meas(est_t, bbas) != abit) & sF).sum(); E_pf += ((meas(est_f, bbas) != abit) & sF).sum()
        thf.append(th_f[0]); thstd.append(np.std(th_t))
        ep = est_t - (IPf @ S) / Df[:, None]
        mah_p += np.real(np.einsum('kn,kl,ln->n', ep.conj(), np.linalg.inv(Cuf + 1e-18 * np.eye(2)), ep)).sum()
        for k in range(2):
            rvp[k, 0] += np.sum(ep[k].real ** 2) / (0.5 * Cuf[k, k].real); rvp[k, 1] += np.sum(ep[k].imag ** 2) / (0.5 * Cuf[k, k].real)
        E_f += ((meas(estf, bbas) != abit) & sF).sum()
        Lf = np.linalg.cholesky(Cwf + 1e-15 * np.eye(2)); efm = 0.0
        for _ in range(a.mc):
            wf = Lf @ (rng.standard_normal((2, C.N_Q)) + 1j * rng.standard_normal((2, C.N_Q))) / np.sqrt(2)
            efm += ((meas((IPf @ S + wf) / Df[:, None], bbas) != abit) & sF).sum()
        E_fm += efm / a.mc
        # ---- measured QBER (sifted) and per-position
        bit_b = meas(est, bbas); s = abas == bbas; err = (bit_b != abit) & s
        E_meas += err.sum(); N_sift += s.sum()
        for b in range(nb):
            sl = slice(edges[b], edges[b + 1]); e_meas[b] += err[sl].sum(); e_cnt[b] += s[sl].sum()
        # ---- model Monte Carlo with the same frame (H,N)
        Lc = np.linalg.cholesky(Cw + 1e-15 * np.eye(2))
        eu = er = 0.0
        for _ in range(a.mc):
            w = Lc @ (rng.standard_normal((2, C.N_Q)) + 1j * rng.standard_normal((2, C.N_Q))) / np.sqrt(2)
            z = IP @ S + w
            eu += ((meas(z / D[:, None], bbas) != abit) & s).sum()
            er += ((meas(z, bbas) != abit) & s).sum()
        E_unb += eu / a.mc; E_raw += er / a.mc
        fr_err.append(err.sum()); fr_n.append(s.sum()); fr_pred.append(eu / a.mc / max(s.sum(), 1))
        logP.append(np.log10(np.real(np.diag(P))))
    qm = E_meas / N_sift; qu = E_unb / N_sift; qr = E_raw / N_sift
    fr_err, fr_n, fr_pred = map(np.array, (fr_err, fr_n, fr_pred))
    var_b = np.sum(fr_n * fr_pred * (1 - fr_pred)); disp = np.sum((fr_err - fr_n * fr_pred) ** 2) / max(var_b, 1e-9)
    nfr = len(seen)
    res = dict(tag=a.tag, frames=nfr, sifted=int(N_sift), cfo_hz=float(cfo),
               qber_measured=float(qm), qber_model_unbiased=float(qu), qber_model_raw=float(qr),
               ratio_meas_over_model=float(qm / max(qu, 1e-9)),
               mahalanobis_mean=float(maha / nmaha), mahalanobis_expected=2.0,
               var_ratio_re_A=float(rv[0, 0] / rn), var_ratio_im_A=float(rv[0, 1] / rn),
               var_ratio_re_B=float(rv[1, 0] / rn), var_ratio_im_B=float(rv[1, 1] / rn),
               real_cross_cov_emp_over_pred=float(cross_e / cross_p) if abs(cross_p) > 1e-12 else None,
               frame_dispersion_index=float(disp),
               qber_by_position=[float(e_meas[b] / max(e_cnt[b], 1)) for b in range(nb)],
               phase_dev_std_rad_A=float(np.std(ph_dev[0])), phase_dev_std_rad_B=float(np.std(ph_dev[1])),
               phase_noise_only_rad_A=float(np.sqrt(np.mean(np.square(ph_noise[0])))), phase_noise_only_rad_B=float(np.sqrt(np.mean(np.square(ph_noise[1])))),
               mag_dev_std_A=float(np.std(mag_dev[0])), mag_dev_std_B=float(np.std(mag_dev[1])),
               mag_noise_only_A=float(np.sqrt(np.mean(np.square(ph_noise[0])))), 
               phase_dev_mean_rad_A=float(np.mean(ph_dev[0])), phase_dev_mean_rad_B=float(np.mean(ph_dev[1])),
               resid_var_ratio_re_A=float(rres[0, 0] / max(rres_n, 1)), resid_var_ratio_im_A=float(rres[0, 1] / max(rres_n, 1)),
               resid_var_ratio_re_B=float(rres[1, 0] / max(rres_n, 1)), resid_var_ratio_im_B=float(rres[1, 1] / max(rres_n, 1)),
               cfo_slope_hz_mean_A=float(np.mean(slope[0])), cfo_slope_hz_mean_B=float(np.mean(slope[1])),
               cfo_slope_hz_sem_A=float(np.std(slope[0]) / np.sqrt(max(len(slope[0]), 1))), cfo_slope_hz_std_A=float(np.std(slope[0])),
               noise_guard_diag=[float(v) for v in np.real(np.diag(Ng)) / max(ng_n, 1)], noise_data_diag=[float(v) for v in np.real(np.diag(Nd)) / max(nd_n, 1)],
               noise_data_over_guard=[float(np.real(Nd[k, k]) / nd_n / (np.real(Ng[k, k]) / ng_n)) for k in range(2)],
               noise_corr_guard=float(abs(Ng[0, 1]) / np.sqrt(np.real(Ng[0, 0] * Ng[1, 1]))), noise_corr_data=float(abs(Nd[0, 1]) / np.sqrt(np.real(Nd[0, 0] * Nd[1, 1]))),
               qber_fullR_measured=float(E_f / N_sift), qber_fullR_model=float(E_fm / N_sift), mahalanobis_fullR=float(maha_f / nmaha),
               var_ratio_fullR=[float(v) for v in (rvf / rn).ravel()], noise_corr_matrix_abs=float(abs(Chat[0, 1])),
               qber_phase_track=float(E_pt / N_sift), qber_phase_frame=float(E_pf / N_sift), phase_win=a.phase_win,
               phase_frame_std_rad=float(np.std(thf)), phase_track_inframe_std_rad=float(np.mean(thstd)),
               mahalanobis_phase=float(mah_p / nmaha), var_ratio_phase=[float(v) for v in (rvp / rn).ravel()],
               offdiag_mean=float(np.mean(offd)),
               P_diag_log10_mean=[float(v) for v in np.mean(logP, axis=0)])
    print(f"\n=== FULL-COVARIANCE CHECK  {a.tag}  ({nfr} frames, {N_sift} sifted bits) ===")
    print(f"QBER measured          {100*qm:6.2f} %")
    print(f"QBER model (unbiased)  {100*qu:6.2f} %    <- what the analyzer's decision rule corresponds to")
    print(f"QBER model (raw MMSE)  {100*qr:6.2f} %    <- biased z, as in the first derivation")
    print(f"measured / model       {res['ratio_meas_over_model']:6.2f}   (1.00 = model explains the data)")
    print(f"Mahalanobis mean       {res['mahalanobis_mean']:6.2f}   (expected 2.00; >2 means real noise exceeds the model)")
    print(f"Var ratio emp/pred  stream A re/im {res['var_ratio_re_A']:.2f}/{res['var_ratio_im_A']:.2f}   stream B re/im {res['var_ratio_re_B']:.2f}/{res['var_ratio_im_B']:.2f}  (expected 1.00)")
    print(f"Real cross-cov emp/pred {res['real_cross_cov_emp_over_pred']}   (expected 1.00)")
    print(f"Frame dispersion index {disp:6.2f}   (1.00 = errors binomial; >1 = drift / bursts)")
    print(f"Per-frame phase offset (LS fit) std, rad:  A {res['phase_dev_std_rad_A']:.3f} (noise-only {res['phase_noise_only_rad_A']:.3f})   B {res['phase_dev_std_rad_B']:.3f} (noise-only {res['phase_noise_only_rad_B']:.3f})   mean A {res['phase_dev_mean_rad_A']:+.3f} B {res['phase_dev_mean_rad_B']:+.3f}")
    print(f"Per-frame gain error std:                  A {res['mag_dev_std_A']:.3f}   B {res['mag_dev_std_B']:.3f}   (noise-only ~ {res['mag_noise_only_A']:.3f})   mean |off-diag| leakage {res['offdiag_mean']:.3f}")
    print(f"Residual after per-frame 2x2 fit / model (1.00 = only H errors left):  A re/im {res['resid_var_ratio_re_A']:.2f}/{res['resid_var_ratio_im_A']:.2f}   B re/im {res['resid_var_ratio_re_B']:.2f}/{res['resid_var_ratio_im_B']:.2f}")
    print(f"In-frame phase slope as CFO error, Hz:  A {res['cfo_slope_hz_mean_A']:+.2f} +/- {res['cfo_slope_hz_sem_A']:.2f} (frame-to-frame std {res['cfo_slope_hz_std_A']:.2f})   B {res['cfo_slope_hz_mean_B']:+.2f}")
    print(f"Receive noise power per RX antenna (data slots / guard slots):  RX0 {res['noise_data_over_guard'][0]:.2f}   RX1 {res['noise_data_over_guard'][1]:.2f}   (1.00 = guard estimate is right)")
    print(f"Receive-noise correlation |rho| between RX0 and RX1:  guard {res['noise_corr_guard']:.3f}   data {res['noise_corr_data']:.3f}   (0 = independent, as the model assumes)")
    print(f"--- decoder with the FULL noise covariance (pooled |rho|={abs(Chat[0,1]):.2f}) ---")
    print(f"QBER measured (full-R MMSE) {100*res['qber_fullR_measured']:5.2f} %   model (full-R) {100*res['qber_fullR_model']:5.2f} %   [diagonal-R decoder: {100*qm:5.2f} %]")
    print(f"Mahalanobis (full-R) {res['mahalanobis_fullR']:.2f} (expected 2.00)   var ratio A re/im {res['var_ratio_fullR'][0]:.2f}/{res['var_ratio_fullR'][1]:.2f}  B re/im {res['var_ratio_fullR'][2]:.2f}/{res['var_ratio_fullR'][3]:.2f}")
    print(f"--- + blind common-phase correction (full-R decoder) ---")
    print(f"QBER  frame-constant phase {100*res['qber_phase_frame']:5.2f} %   sliding window {a.phase_win}: {100*res['qber_phase_track']:5.2f} %   [full-R only {100*res['qber_fullR_measured']:5.2f} %, model {100*res['qber_fullR_model']:5.2f} %]")
    print(f"Mahalanobis {res['mahalanobis_phase']:.2f}   var ratio A re/im {res['var_ratio_phase'][0]:.2f}/{res['var_ratio_phase'][1]:.2f}  B re/im {res['var_ratio_phase'][2]:.2f}/{res['var_ratio_phase'][3]:.2f}   tracked phase: frame-to-frame std {res['phase_frame_std_rad']:.3f} rad, in-frame std {res['phase_track_inframe_std_rad']:.3f} rad")
    print("QBER vs position in frame (" + str(nb) + " bins): " + " ".join(f"{100*v:5.1f}" for v in res['qber_by_position']))
    Path(f"covcheck_{a.tag}.json").write_text(json.dumps(res, indent=1)); print(f"wrote covcheck_{a.tag}.json")

if __name__ == "__main__":
    main()
