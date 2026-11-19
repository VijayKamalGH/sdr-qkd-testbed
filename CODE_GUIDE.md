# SDR 2x2 MIMO spatial-qubit BB84 testbed: code behind the manuscript

READ START_HERE.md FIRST. Raw captures (`*.c64`, about 208 MB per receive file) are NOT included. Names used in the manuscript:
`H194E_V18Z34_<TAG>_ON_RX0.c64` / `_RX1.c64`. Each script below is run from a folder that holds the helper modules it imports.

## lab_capture_and_analysis (Sender PC = TX, Receiver PC = capture + analysis)
- `H194E_Z38_COMMON.py` frame and qubit definitions (shared by TX and analyser). `H194E_GUARD` env var changes the guard length (default 64).
- `H194E_BPSK_TX_V18Z38_MIMO_QKD.py` transmitter (Sender). Needs the patched gr-osmosdr for two-channel TX:
  `export PYTHONPATH=$HOME/opt/gr-osmosdr-mimo-txcount-fixed/lib/python3.12/site-packages:$PYTHONPATH`
  `export LD_LIBRARY_PATH=$HOME/opt/gr-osmosdr-mimo-txcount-fixed/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH`
  then `python3 H194E_BPSK_TX_V18Z38_MIMO_QKD.py --seconds 90 --frames 256 --gain 14` (the lab `run_tx.sh` launcher does the exports and checks that `osmosdr.__file__` contains `mimo-txcount-fixed`).
- `H194E_V18Z34_CAPTURE.py --state ON --tag X --seconds 13` capture on the Receiver PC (calls `H194E_BB84_RF_DUAL_CAPTURE_V4.py`, now included, md5 162f39c6...).
- `H194E_V18Z37_MIMO_ANALYZE.py` DSP helpers; `H194E_P16B_BB84_CASCADE_UDP.py` Cascade and privacy amplification.
- `H194E_V18Z38_QKD_ANALYZE.py` analyser: `python3 H194E_V18Z38_QKD_ANALYZE.py --rx0 X_RX0.c64 --rx1 X_RX1.c64 [--detector ZF]`.
  This folder now holds the FROZEN lab copies (see FROZEN_MD5SUMS.txt); earlier variants are in `not_frozen_variants/`.
- `H194E_V18Z38_COV_CHECK.py`, `COV_CHECK_zf.py`, `apply_zf.py`, `H194E_V18Z38_NOISE_CORR.py` model-versus-measurement checks (Theorem 1 model, ZF variant, noise correlation).
- `H194E_V18Z34_ANALYZE.py`, `_PRESENCE.py`, `_SWEEP_REPORT.py` earlier sweep and presence reports.

## phaseA_netsquid (lab PC with the NetSquid venv)
BB84, BBM92/E91, QSDC in numpy and NetSquid; `H194E_PA_HYBRID_SWEEP.py` is the hybrid SDR-QBER + frame-loss -> NetSquid sweep (journal Table/Fig. hybrid).

## phaseB_udp
- `H194E_PB_UDP_BB84.py` Phase B (v2, md5 ea88380c...): Sender first, then Receiver.
  `python3 H194E_PB_UDP_BB84.py --role sender --listen 5006 --peer RECEIVER_IP:5005 --n 40000 --qch 0.02 [--q-eve 0.5]`
  `python3 H194E_PB_UDP_BB84.py --role receiver --listen 5005 --peer SENDER_IP:5006 --n 40000 --qch 0.02 [--p-loss 0.05]`
- `H194E_PB2_SDR_BB84.py` Phase B2 on real captures (Receiver first, Sender after):
  `--role receiver --lib <RECEIVER_BOB dir> --listen 5005 --peer SENDER_IP:5006 --rx0 ..._RX0.c64 --rx1 ..._RX1.c64`
  `--role sender --lib <SENDER_ALICE dir> --listen 5006 --peer RECEIVER_IP:5005`

## phaseC_D_tracking_sensing (Receiver PC; import the analyser from `--lib`)
- `H194E_PC_KALMAN.py --lib . --dir . --tag KW1 --qmul 0.25 1` C1 Kalman filter on H (Table C1).
- `H194E_PC_PHASERATE.py --lib . --dir . --tag KW1 --qr 0.1` C2 rate tracker.
- `phase_stats.py KQ4 KW1 ...` phase-step statistics and lag-1 autocorrelation (paths inside the script point to the sandbox; edit `u=` and `sys.path`).
- `H194E_PD2_MOTION.py --lib . --dir . --tags KQ1 ... --csv out.csv` D2 per-window features. `d2_all.csv`, `d2_wide.csv` are the two sessions' outputs used in the paper.
- `H194E_PD1_SENSING.py` D1 sensing statistics (journal sensing observations).

## figures_and_stats
`fig.py`, `skr.py`, `sw.py`, `fig2.py`, `sweep.py` earlier fit/sweep figures. `model_ZF/zfmodel.py` ZF model.

## Not in this package (honest list)
- The scripts that drew `fig_dec.png`, `fig_hyb.png`, `fig_zf.png`, `fig_zf2.png` were run inline earlier and not saved as files; the PNGs are in the Overleaf package. They can be regenerated if you want (ask).
- Lab-only helper scripts written from pasted heredocs (D1 helpers `H194E_PD1_DIAG/ALIAS/DOA/SYNC/PILOTS/TONE/SHAPE.py`, `sweep.sh`, `analyse_S.sh`, `epos.sh`, `run_tx.sh`) exist on the lab PCs and in the chat; they are not in this zip.
- The Phase C/D figure `fig_cd.png` was drawn from `d2_all.csv`, `d2_wide.csv` and the error counts in the paper (Table C1/C2).

## Added in v19
- `figures_and_stats/geometry_model.py`, `cond_zf_gain.py`, `fig_zf.py`, `fig_zf2.py`, `fig_dec.py` and their data files (`zf_table.csv`, `fullR_phase_table.csv`); see `figures_and_stats/README.md`.
- `results_cache/geometry_trials.csv`: the complete geometry-trial captures (polarisation, 5 m, outdoor to indoor, room to room) from the status summary.
