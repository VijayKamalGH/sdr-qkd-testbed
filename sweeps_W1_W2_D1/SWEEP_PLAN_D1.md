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

## Amendment 1 (2026-11-10, before any D sweep capture was analysed; no D sweep data seen)
Two attempts at 1 m produced no usable captures: the full sweep D1M (19 items) and a one-capture test D1T (gain 8). In every ON capture the power equalled the noise-only power and there was no tone at +100 kHz, so no signal reached the Receiver (Sender transmit program reported active; physical path suspected: connectors after moving the antennas; the operator's exact fix is to be recorded here). Both folders are kept (sweep_D1M_failed1, sweep_D1T). After the connections were checked, a two-item test D1U at 1 m gave, for one capture each, post-MMSE SINR 25.8 dB at gain 30 (QBER 0.00%, key 22\,213 bits) and 5.5 dB at gain 8 (QBER 6.93% MMSE, 8.11% ZF, no key). Prediction P1 expected about 11.7 dB at gain 8 (5.7 dB at 2 m plus 6 dB); the observed 5.5 dB is about 6 dB lower. This is one capture and is reported as such.
Changes made because of D1U (and not because of any sweep result):
- Gains at 1 m become 6, 8, 10, 12, 14 dB (was 2, 4, 6, 8, 10), so that the SINR range of about 3-12 dB is still covered. The seed 20261111 and the tag D1M are unchanged.
- Before each of the 5 m and 10 m sweeps a two-capture pilot (5 m: gains 14 and 22, tag D5U; 10 m: gains 20 and 30, tag D10U) fixes the gain grid in a further amendment. Pilot captures are reported but not used in the endpoints.
- Predictions P1-P3 and all endpoints are unchanged; P1 will be reported as it comes out.

## Amendment 2 (2026-11-10, before the D1N sweep; no D sweep data seen)
The second 1 m attempt (tag D1M, gains 6-14) reused a tag whose raw captures from the first attempt were still in the working folder; the runner analysed those stale files (the four noise-only results matched the first attempt to every digit, and the file timestamps were 12:31-12:34). That attempt is void. The stale files were moved to stale_D1M, the results folders are kept as sweep_D1M_failed1, _failed2 and _failed3, and the 1 m sweep is rerun under a new tag D1N with the same gains (6, 8, 10, 12, 14 dB), repeats, order seed 20261111 and endpoints. Rule added: a tag is never reused, and any raw capture file of an earlier run with the same tag is moved away before a run (check timestamps).

## Amendment 3 (2026-11-10, after the 1 m sweep D1N and the 5 m pilot D5U; no 5 m sweep data seen)
Results of D1N (13 of 15 decodable, 2 at 6 dB without frames) and of the two-capture pilot D5U at 5 m (gain 22: no key, MMSE QBER 11.17%, mean post-MMSE SINR 7.2 dB with stream A 9.1 dB and stream B 3.7 dB; gain 14: no frames) are reported separately. They show that SINR does not follow free-space loss (P1 not met at 1 m: observed +1.2 dB against +6 dB predicted) and that gain 14 dB is undecodable at 5 m.
Change for 5 m, based on the pilot and not on any 5 m sweep result: gains 20, 22, 24, 26, 28 dB (was 16-24), tag D5M, order seed 20261112, 3 repeats, --keep. The 10 m grid is fixed in a further amendment after its pilot (D10U, gains 28 and 34 dB). Added exploratory analysis (not a primary endpoint, labelled exploratory in any report): QBER predicted from the two post-MMSE stream SINRs separately, fitted on W1 and W2. Predictions P1-P3 and endpoints 1-5 are unchanged.

## Amendment 4 (2026-11-10, after the 5 m sweep D5M; no 10 m data and no control data seen)
D5M gave 10 of 15 decodable captures (gain 20: 0 of 3, gain 22: 1 of 3). Distance, noise condition and time of day are confounded in the D runs: the noise-only |rho| fell from about 0.5 (W2, 2 m, 9 Nov evening) through 0.70 to 0.35 (1 m, 12:57-16:40) to 0.17-0.26 (5 m, 17:48-18:02), and the effective gain offset relative to 2 m was -1.6 dB at 1 m and +12.3 dB at 5 m, not the -6 dB and +8 dB predicted (P1 not met at either distance).
Added before any further capture: a 2 m control sweep in the same room on the same day, tag D2C, gains 8, 10, 12, 14 dB, 3 repeats, order seed 20261114, --keep, Sender pair back at 2.0 m centre to centre, all else as in D1N and D5M. Its purpose is to test whether the 2 m QBER-versus-SINR curve of W1 and W2 still holds on the day of the D runs, and to compare the noise-only |rho| and phase with the D runs. Endpoints: per-capture ratio to the W1/W2 curve (median and bootstrap 95% interval) and the SINR offset at equal gain relative to W2. The 10 m pilot (D10U, gains 28 and 34 dB) and the 10 m sweep follow after the control; the 10 m grid is fixed in a further amendment. Predictions and endpoints P1-P3, 1-5 unchanged.

## Amendment 5 (2026-11-10, after the 2 m control D2C; no placement-test data seen)
D2C (12 of 12 decodable) showed that putting the Sender pair back at 2.0 m gave a different channel from W1/W2: median condition number 12.1 (W1 3.8, W2 2.9), stream SINR imbalance 5.3 dB (W2 1.2 dB), SINR at equal gain +1.8 dB above W2, QBER at equal mean SINR 4.5 times the W curve (interval 3.5-5.0; 1.38, interval 1.22-1.53, when predicted from the two stream SINRs separately). The 10 m pilot and sweep are cancelled; 1 m, 2 m (control) and 5 m are the distances reported. No further distance sweeps are planned.
Added: a placement repeatability test. Three placements of the Sender pair at 2.0 m (centre to centre, same height, orientation facing the Receiver pair): after each run the pair is moved at least 1 m away and set back to 2.0 m with a tape measure. Each placement is one run with gain 12 dB, 3 repeats, noise-only captures before and after, tags D2P1, D2P2, D2P3, --keep. Gain 12 dB is chosen because both W2 and D2C give decodable captures with 1-1.2% MMSE QBER there. Descriptive endpoints, no pass/fail rule: per placement the mean post-MMSE SINR, stream imbalance, condition number, noise-only |rho| and phase, MMSE and ZF QBER; the standard deviation across placements (3 placement means) against the standard deviation within a placement (3 captures each). Results are reported as they come out.
