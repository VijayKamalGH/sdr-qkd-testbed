# Distance sweep D: analysis plan fixed before any capture
Written 2026-11-10 (before the first D capture). Keep this file unchanged; its SHA-256 timestamps the plan.

## Purpose
Test the claim that measured post-MMSE SINR, not nominal gain or geometry, determines the QBER: when the Sender-Receiver distance changes, QBER against measured SINR should stay on the curve found at 2 m (W1 and W2).

## Frozen items (no change during the sweep)
- Same analyser, runner, transmitter, seed (20261030), 256 frames, amplitude 0.14, 13 s captures and 5 s settle as W1/W2 (analyser md5 7ed389b173f821cca10a69258617d37c; Z37 md5 2020b33fa9cafbd082b47e23d27d6771; runner md5 4f43b09ad7d8ba7b43e4f2db54e1f476; model zfmodel.py md5 ab84a1d388bef3b8e0bb392bd9d8684e).
- Geometry except distance: Quasar SDR PBTOA 5002000 antennas at 0 deg polarisation, spacing 16.4 cm at each end, same room, same heights, same pair orientation facing the other pair, same cables. Only the Sender's antenna pair is moved; distance measured between the centres of the two pairs.
- The operator stays in one fixed place; doors, people and antenna touches are logged by hand with the time.

## Design
| Distance | Tag | Gains (dB) | Order seed |
|---|---|---|---|
| 1 m | D1M | 2, 4, 6, 8, 10 | 20261111 |
| 5 m | D5M | 16, 18, 20, 22, 24 | 20261112 |
| 10 m | D10M | 22, 24, 26, 28, 30 | 20261113 |
3 repeats per gain (15 captures per distance), shuffled, with a noise-only capture first, after every 6 captures and last. Gains are chosen from the 2 m result (SINR about gain - 3 dB) and free-space loss, to cover about 4-13 dB SINR; they are not adjusted after seeing data. All raw captures are kept (--keep).

## Predictions (stated before data)
P1. At equal gain the mean SINR differs from the 2 m value by -20 log10(d/2 m) dB: +6 dB (1 m), -8 dB (5 m), -14 dB (10 m).
P2. MMSE QBER against measured SINR lies on the 2 m curve: log-linear fit of ln(QBER) on SINR over W1 and W2 pooled (decodable captures, SINR 3-12 dB).
P3. MMSE gives lower QBER than ZF in at least 80% of decodable captures at each distance.

## Primary endpoints
1. Per distance, observed minus predicted SINR offset at equal gain (mean over captures), with a bootstrap 95% interval. Agreement: within +-3 dB.
2. For decodable captures with SINR 5-11 dB: ratio of measured MMSE QBER to the 2 m curve at the same SINR; median and bootstrap 95% interval per distance. Agreement: interval within 0.67-1.5 (W1 and W2 differ by 0.7-0.9 within this range).
3. Counts of captures with a key (Q_up <= 11%) for MMSE and ZF; ZF/MMSE ratio per capture.
4. Noise-only |rho| and inter-antenna phase per distance (expected to change with position; reported, not used to exclude).
5. Optional, on kept captures: H194E_V18Z38_COV_CHECK.py measured/model ratio as in W2.

## Rules
- A capture is decodable if at least 200 frames synchronise and the analyser finishes. Any other exclusion is reported with its reason; there are no others.
- Wilson intervals on error counts per capture. No result is dropped because it disagrees with the plan.
- If a distance cannot be set up as listed, that distance is not run, and the change is recorded before capturing.
- Negative or mixed results are reported as they are.
