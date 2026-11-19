# SDR 2x2 MIMO spatial-qubit BB84 / BBM92 emulation testbed

Code, figures and analysis files behind the manuscript in `paper/main.tex` (version 19). The radio carries **classical symbols**: the QBER is a
classical bit-error rate expressed in BB84 terms and **no quantum-security claim is made**.

## Status
Pre-submission draft. Results come from one laboratory, single captures per condition, and several steps were exploratory (not pre-registered); see the
Discussion and Limitations section of the paper. Nothing here has been peer reviewed.

## Layout
| Folder | Content |
|---|---|
| `paper/` | `main.tex` (v19), the six result figures, the two setup photos. Build with `pdflatex main.tex` twice. |
| `lab_capture_and_analysis/` | Transmitter, capture and analyser (frozen copies, checksums in `FROZEN_MD5SUMS.txt`). |
| `sweeps_W1_W2_D1/` | Sweep runner, pre-registered plan files and amendments, W1/W2 analysis. |
| `results_cache/` | Per-capture results (`w1w2_table.json`, geometry trials, covariance checks). |
| `phaseA_netsquid/`, `phaseB_udp/`, `phaseR_radio_public_channel/`, `phaseC_D_tracking_sensing/`, `model_ZF/`, `figures_and_stats/` | Hybrid NetSquid run, public channel over UDP and over the radio, tracking and sensing, ZF model, fit scripts. |
| `grc_demo/` | GNU Radio Companion demonstration flowgraphs (Demos 1-6) and the blocks behind them. For demonstration only; the paper's numbers come from the frozen analyser, not from these flowgraphs. |
| `analyzer_test/` | Spectrum-analyser check of the transmitter: peak level against TX gain (14-30 dB), the four screens, and `rxpower.py` (power of a stored capture in dBFS). |
| `docs/` | `GRC_demo_guide.pdf`, a short guide to the demonstrations. |

Start with `START_HERE.md` (what to run and what to expect) and `CODE_GUIDE.md` (file-by-file notes).

## Not included
- Raw captures (`*.c64`, about 208 MB per receive file) and transmit waveform files; they stay on the lab PCs (GitHub limits files to 100 MB).
- `fig_hyb.png` cannot be regenerated here: its per-capture hybrid results were not saved, and NetSquid and the 19 capture files are needed (`phaseA_netsquid/H194E_PA_HYBRID_SWEEP.py` produces the numbers). Panel (b) of `fig_dec.png` (noise correlation of the sender-off captures) has no saved data either. The PNGs are in `paper/`.
- Re-created plotting scripts in `figures_and_stats/` (output in `figures_and_stats/regenerated/`, never over `paper/`): `fig_zf2.py` (same data as the paper table, exact), `fig_dec.py` (panel a only, same data points), `fig_zf.py` (theory curves: same shape, numbers differ slightly from the paper text because the original random channels were not saved).
- Some lab-only helper scripts (see the last section of `CODE_GUIDE.md`).

## Integrity
`MANIFEST_SHA256.txt` lists the SHA-256 of every file in this folder. The frozen lab code is also covered by `FROZEN_MD5SUMS.txt`.

## Licence
Not set. Add a licence file before publishing.
