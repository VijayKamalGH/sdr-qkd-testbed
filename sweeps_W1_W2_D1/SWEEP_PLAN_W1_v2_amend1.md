# Fresh sweep W1: analysis plan fixed before any capture
Written 2026-11-09 (before the first W1 capture). Keep this file unchanged; its SHA-256 (see the covering message) timestamps the plan.

## Purpose
Test, on captures taken after the receiver corrections were fixed, whether (1) the measured MMSE QBER agrees with the post-MMSE model that uses the capture's own channel and noise covariance, (2) MMSE gives lower QBER and more key-yielding captures than ZF, and (3) the earlier findings hold on new data.

## Frozen items (no change during the sweep)
- Analyser on the Receiver PC: H194E_V18Z38_QKD_ANALYZE.py md5 7ed389b173f821cca10a69258617d37c, H194E_V18Z37_MIMO_ANALYZE.py md5 2020b33fa9cafbd082b47e23d27d6771 (MMSE with pooled full noise covariance and blind common-phase correction; ZF run with --detector ZF).
- Runner H194E_SW_SWEEP.py md5 4f43b09ad7d8ba7b43e4f2db54e1f476; transmitter H194E_BPSK_TX_V18Z38_MIMO_QKD.py, seed 20261030, 256 frames, amplitude 0.14.
- Model: Theorem 1 of manuscript v6 (zfmodel.py md5 ab84a1d388bef3b8e0bb392bd9d8684e); the comparison code applied is the one used for the v6 tables. Any change made after seeing the data will be reported together with the unchanged result.

## Design
- TX gains 4, 6, 8, 10, 12, 14 dB, 3 repeats each (18 captures), order shuffled with seed 20261109, plus a noise-only capture (transmitter off) first, after every 6 captures and last (4 captures).
- Geometry unchanged: Sender TX1/TX2 and Receiver RX1/RX2, antennas 0 deg polarisation, spacing 16.4 cm at each end, 2 m apart. The operator stays in one fixed place during the run; the doors, people nearby and any antenna touch are logged by hand with the time.
- 13 s capture per item; 5 s settle after the transmitter starts.

## Primary endpoints
1. For each decodable capture: ratio R = measured MMSE QBER / model QBER. Report median, range and a bootstrap 95% interval over captures. Expected from the earlier sweep: median within 0.85-1.20.
2. Number of captures with a key (Q_up <= 11%) for MMSE and for ZF; ZF/MMSE QBER ratio per capture. Expected: ratio > 1 in at least 80% of decodable captures.
3. QBER against measured post-MMSE SINR (all captures, one plot).

## Rules
- A capture is decodable if at least 200 frames synchronise and the analyser finishes. Any other exclusion is reported with its reason; there are no others.
- Noise-only captures give the receive-noise correlation (rho, phase) before, during and after, to check for drift; a change of |rho| by more than 0.15 between the first and last noise-only capture is reported as a changed condition.
- Per-capture confidence intervals: Wilson interval on the error count over sifted bits. No result is dropped because it disagrees with the model.
- Negative or mixed results will be reported as they are.

## Amendment 1 (2026-11-09, before the first W1 capture)
The original plan listed gains 6-16 dB. A 3-item check run (tag T1: noise-only, 14 dB, noise-only) showed MMSE QBER 0.11% at 14 dB with post-MMSE SINR 10.7 dB and noise-only correlation |rho| = 0.23-0.28, a quieter condition than in earlier sweeps, so 14-16 dB would give almost no errors. The gain grid is therefore changed to 4-14 dB. The change is based only on the T1 check run, not on any W1 data. The original text (SHA-256 4a26d2fe39a0d99259e87ad6aa76e1e7e69c304f55e71124197ddf78f88a2e1c) is kept as SWEEP_PLAN_W1_v1_original.md.
