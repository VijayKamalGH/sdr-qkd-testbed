# figures_and_stats
| Script | What it does | Needs |
|---|---|---|
| `geometry_model.py` | Equations of Sec. IV-M of the paper evaluated on the geometry-trial numbers: free-space loss versus measured SINR drop, SINR-versus-gain slope, line-of-sight 2x2 conditioning versus spacing, ideal polarisation model, QBER from per-stream SINR (Theorem 1), ZF penalty, abort margin. The measured numbers are typed in from `results_cache/geometry_trials.csv`. | numpy, scipy |
| `cond_zf_gain.py` | Per-frame complex condition number, diagonal/off-diagonal power and ZF SINR of one capture, by wrapping the frozen receiver (nothing edited). Tested only on a synthetic capture with known H (complex cond 3.229 true, 3.23 recovered); not run on a real capture here. | raw `.c64` captures (not in this repository) |
| `fig_zf2.py`, `fig_zf.py`, `fig_dec.py` | Re-created plots, see the top-level README for what is exact. | `zf_table.csv`, `fullR_phase_table.csv` |
| `fig.py`, `fig2.py`, `skr.py`, `sw.py`, `sweep.py` | Earlier fit and sweep scripts. | see `CODE_GUIDE.md` |
Run each script from this folder: `python3 geometry_model.py`.
