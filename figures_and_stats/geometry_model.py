#!/usr/bin/env python3
"""Closed-form relations used in the geometry subsection of the paper, evaluated for the Tables of the status summary.
numpy/scipy only. Prints (1) free-space loss and the measured SINR drop, (2) the SINR-versus-gain slope of the
room-to-room set, (3) the line-of-sight 2x2 channel of two parallel arrays and its complex condition number versus spacing,
(4) the ideal linear-polarisation model against the measured SINR change, (5) QBER predicted from the measured per-stream
SINR (Theorem 1 with diagonal H) against the measured QBER.  Every measured number is typed in from the status tables."""
import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model_ZF"))
import numpy as np
from scipy.stats import norm
import zfmodel as z
lam = 299792458/915e6                        # 0.3277 m
fspl = lambda d: 20*np.log10(4*np.pi*d/lam)
print(f"lambda = {100*lam:.1f} cm")
# ---- (1) path loss
ref_g24 = np.mean([23.6, 22.1])              # 2 m, gain 24, 0/0 references (mean SINR, dB)
meas = {"5 m indoor g24": (5, np.mean([(10.8+7.0)/2, (12.0+8.6)/2])),
        "~11 m room-to-room g24": (11, np.mean([(8.7+4.7)/2, (9.3+4.9)/2]))}
print("\n(1) free-space loss relative to 2 m, against measured mean-SINR drop at gain 24 (2 m reference %.1f dB)" % ref_g24)
for k, (d, s) in meas.items():
    print(f"  {k:24s} FSPL step {fspl(d)-fspl(2):5.1f} dB   measured drop {ref_g24-s:5.1f} dB   excess {ref_g24-s-(fspl(d)-fspl(2)):5.1f} dB")
# ---- (2) SINR vs gain, room to room
mean = lambda *v: float(np.mean(v))
S = {36: mean((20.1+21.1)/2, (21.2+17.3)/2), 30: mean((13.3+9.9)/2, (13.8+9.9)/2), 24: mean((8.7+4.7)/2, (9.3+4.9)/2)}
print("\n(2) room to room, mean of per-capture mean SINR:", {g: round(v, 2) for g, v in S.items()})
print(f"  36->30: {S[36]-S[30]:.2f} dB per 6 dB   30->24: {S[30]-S[24]:.2f} dB per 6 dB   36->24: {S[36]-S[24]:.2f} dB per 12 dB  (kappa={(S[36]-S[24])/12:.2f})")
# ---- (3) LOS channel of two broadside-parallel arrays, spacing s at both ends, range D
def los(s, D, extra_pol=None):
    yt = np.array([-s/2, s/2]); yr = np.array([-s/2, s/2])
    d = np.sqrt(D**2 + (yr[:, None]-yt[None, :])**2)
    return np.exp(-2j*np.pi*d/lam)/d*D                      # amplitude normalised to the broadside path
print("\n(3) pure line-of-sight, D = 2 m: complex condition number versus spacing")
print("   s/lambda   delta(rad)  kappa_c   kappa_c(dB)   printed index of |H|")
for m in (0.5, 1, 2, 4, 6, 8):
    s = m*lam; H = los(s, 2.0); sv = np.linalg.svd(H, compute_uv=False); sa = np.linalg.svd(np.abs(H), compute_uv=False)
    dl = np.angle(H[0, 1]/H[0, 0])
    print(f"   {m:5.1f}     {dl:8.3f}   {sv[0]/sv[1]:8.1f}   {20*np.log10(sv[0]/sv[1]):7.1f}      {sa[0]/sa[1]:.1f}")
print(f"   orthogonality (kappa_c = 1) first reached at s = sqrt(lambda D/2) = {np.sqrt(lam*2/2):.3f} m = {np.sqrt(lam*2/2)/lam:.2f} lambda")
# ---- (4) ideal linear polarisation
print("\n(4) ideal linear polarisation, p_ij = cos(theta_tx_j - theta_rx_i); mean-entry power relative to 0/0 and |p| rank")
cases = {"+-90/0": (90, 0), "+-90/+-90": (90, 90), "+-45/0": (45, 0), "+-45/+-45 matched": (45, 45)}
meas_d = {"+-90/0": 12.3, "+-90/+-90": 14.6, "+-45/0": 15.2, "+-45/+-45 matched": 13.4}
for k, (tt, rr) in cases.items():
    P = np.array([[np.cos(np.radians(t-r)) for t in (tt, -tt)] for r in (rr, -rr)])
    pw = np.mean(P**2); sv = np.linalg.svd(P, compute_uv=False)
    print(f"  {k:18s} mean power {10*np.log10(max(pw,1e-12)):6.1f} dB  sv {sv[0]:.2f},{sv[1]:.2f}   measured mean SINR {meas_d[k]:.1f} dB = {meas_d[k]-ref_g24:.1f} dB vs reference")
# ---- (5) QBER from measured per-stream SINR, diagonal H (unit gains), independent noise
def q_from_sinr(ga, gb):
    out = []
    for g in (ga, gb):
        pass
    P = np.diag([1/(1+10**(ga/10)), 1/(1+10**(gb/10))])      # post-MMSE error covariance for orthogonal streams
    H = np.diag([np.sqrt(10**(ga/10)), np.sqrt(10**(gb/10))]); R = np.eye(2)
    e = z.eqs(H, R); return z.qber(e["MMSE"], H, R)
print("\n(5) QBER predicted from measured per-stream SINR (orthogonal streams, independent noise) vs measured")
rows = [("DIST5B g24", 12.0, 8.6, 2.94), ("DIST5G30A", 16.4, 12.2, 1.61), ("DIST5G30B", 14.4, 9.6, 4.82), ("DIST5A g24", 10.8, 7.0, 6.41),
        ("1912 out->in g36", 14.8, 14.7, 0.17), ("ROOM30A", 13.3, 9.9, 0.22), ("ROOM30B", 13.8, 9.9, 0.17), ("ROOM24A", 8.7, 4.7, 5.15),
        ("ROOM24D", 9.3, 4.9, 5.01), ("ROOM36A", 20.1, 21.1, 0.07)]
print("   capture            SINR A/B    model %   measured %")
for t, a, b, q in rows:
    print(f"   {t:18s} {a:5.1f}/{b:4.1f}   {100*q_from_sinr(a, b):7.3f}   {q:6.2f}")
# ---- (6) illustration only: frame-to-frame SINR spread (dB, Gaussian) raises the mean QBER above the value at the mean SINR.
#      The spread is NOT measured (the analyser reports only the mean), so these are what-if values, not results.
print("\n(6) what-if: QBER averaged over frames whose SINR (dB) is Gaussian about the measured mean, spread sigma (not measured)")
gh = np.polynomial.hermite_e.hermegauss(15); wts = gh[1]/gh[1].sum()
for t, a, b, q in rows[:5] + rows[7:9]:
    v = []
    for sg in (0, 2, 3, 4):
        v.append(sum(w*q_from_sinr(a+sg*x, b+sg*x) for x, w in zip(gh[0], wts)))
    print(f"   {t:18s} measured {q:5.2f}%   sigma 0/2/3/4 dB: " + " / ".join(f"{100*x:.3f}" for x in v) + " %")
# ---- (7) ZF noise-gain penalty from the complex condition number (R = N I, fixed ||H||_F):
#          sum_k 1/gamma_k^ZF = N (1+kappa^2)^2 / (||H||_F^2 kappa^2), minimum 4N/||H||_F^2 at kappa = 1
print("\n(7) ZF penalty (1+k^2)^2/(4k^2) relative to orthogonal streams")
for k in (1.5, 3.3, 3.6, 54.3):
    print(f"   kappa {k:5.1f}: {10*np.log10((1+k*k)**2/(4*k*k)):5.1f} dB")
# ---- (8) abort margin of the marginal room-to-room captures (sifted bits assumed = 268 frames x 272 qubits / 2)
print("\n(8) abort rule, Q_up = Q + sqrt(ln(1/eps)/(2 n_t)), eps = 1e-6, n_t = floor(0.1 n_s)")
ns = int(268*272/2); nt = int(0.1*ns); mg = np.sqrt(np.log(1e6)/(2*nt))
print(f"   n_s ~ {ns}, n_t = {nt}, margin {100*mg:.2f} points; largest Q for a key {100*(0.11-mg):.2f}%")
for t, q in (("ROOM24A", 5.15), ("ROOM24D", 5.01)):
    print(f"   {t}: Q_up = {q+100*mg:.2f}%")
