# SDR 2x2 MIMO spatial-qubit BB84/BBM92 -- reproduction + demo bundle (manuscript v18)

## What is in the folders
- paper/                         main.tex (manuscript v18) + 6 figures + 2 setup photos. `pdflatex main.tex` twice (or Overleaf).
- lab_capture_and_analysis/     FROZEN lab code (md5 in FROZEN_MD5SUMS.txt): transmitter, capture, analyser. Older variants: not_frozen_variants/.
- sweeps_W1_W2_D1/              sweep runner, plan files (+amendments; SWEEP_PLAN_D1.md SHA-256 cc0a68e0...), W1/W2 analysis.
- results_cache/                W1/W2 per-capture results (w1w2_table.json), distance manifests, COV_CHECK jsons.
- phaseA_netsquid/, phaseB_udp/, phaseR_radio_public_channel/, phaseC_D_tracking_sensing/, model_ZF/, figures_and_stats/
NOT in the bundle: raw captures (*.c64, ~208 MB each) -- they stay on the Receiver Desktop PC.

## Python for the laptop demos (no radio): Python 3.10, numpy, scipy
python3 -c "import numpy, scipy; print('ok')"

## DEMO 1  public channel over UDP (2 laptops; start the Receiver first)
cd phaseB_udp
Receiver: python3 H194E_PB_UDP_BB84.py --role receiver --listen 5005 --peer SENDER_IP:5006 --n 40000 --qch 0.02
Sender  : python3 H194E_PB_UDP_BB84.py --role sender   --listen 5006 --peer RECEIVER_IP:5005 --n 40000 --qch 0.02
 clean run         -> same Qhat 0.024036 and same key 7118 bits on both
 Eve (q=0.5)       -> add `--q-eve 0.5` to BOTH commands -> Qhat 0.1337, both abort, no key
 5% frame loss     -> add `--p-loss 0.05` to the Receiver command only -> same key 7118, 4 frames lost and resent
(Tested on two lab laptops on 2026-11-11.)

## DEMO 2  full radio protocol on a synthetic channel, BB84 then BBM92 (one laptop, ~50 s per protocol)
cd phaseR_radio_public_channel && bash runsim.sh
tail -n 2 rcv_bb84.log snd_bb84.log rcv_bbm92.log snd_bbm92.log   -> same key 4436 bits on both sides
(this folder has its own simlib/ copies for the synthetic mode; do not replace them)

## DEMO 3  fresh-sweep results table (W1/W2)
cd results_cache
python3 -c "
import json
d=json.load(open('w1w2_table.json'))
for k in d:
    print(k)
    for r in d[k]: print(r['tag'],r['gain'],round(r['sinr'],1),'QBER MMSE %.4f ZF %.4f'%(r['qm'],r['qz']),'key',r['key_m'],r['key_z'])
"

## DEMO 4  decode a REAL stored RF capture on a laptop (the headline demo)
Needs the capture pair from the Desktop PC (RECEIVER_BOB): H194E_V18Z34_SWW203_ON_RX0.c64 and ..._RX1.c64 (208 MB each).
Put them in one folder together with these frozen files from lab_capture_and_analysis/ of THIS bundle:
 H194E_V18Z38_QKD_ANALYZE.py  H194E_V18Z37_MIMO_ANALYZE.py  H194E_Z38_COMMON.py  H194E_P16B_BB84_CASCADE_UDP.py
(Copy over the lab network: on the Desktop `cd ~/replay_pack; python3 -m http.server 8000`, on the laptop
 `wget -c -np -r -nd -R "index.html*" http://DESKTOP_IP:8000/`. A 62 GB USB stick failed to mount (exFAT/NTFS driver).)
Run:
 python3 H194E_V18Z38_QKD_ANALYZE.py --rx0 H194E_V18Z34_SWW203_ON_RX0.c64 --rx1 H194E_V18Z34_SWW203_ON_RX1.c64
 python3 H194E_V18Z38_QKD_ANALYZE.py --rx0 ... --rx1 ... --detector ZF
Expected (verified on the Receiver laptop 2026-11-12, identical to the paper's W2 row SWW203):
 MMSE: 268 frames, QBER 0.05% (19 errors), SINR A +10.7 / B +12.1 dB, cond 2.85, key 22057 bits
 ZF  : QBER 0.08% (27 errors), key 21976 bits

## LIVE 2x2 TRANSMISSION -- Desktop PCs only (what we learned on the laptops)
Receiver laptop: works for capture ONLY after installing the matching gr-osmosdr in /usr/local
 (the Ubuntu package gr-osmosdr 0.2.3 segfaulted against the /usr/local GNU Radio 3.10.5.1 build).
Sender laptop: the radio enumerated and transmitted without USB errors in 30 s runs at gains 8, 12, 14 and 24, but 90 s runs dropped the radio (LIBUSB_ERROR_NO_DEVICE),
 and the received signal timing did not match the intended waveform (guard gaps ~3 ms every ~24 ms instead of 6.4 ms every 48 ms; frame sync found no pilots).
 There is no patched gr-osmosdr (mimo-txcount-fixed) on the laptops. Do the live 2x2 transmission on the Desktop PCs:
Sender shell:
  export PYTHONPATH=$HOME/opt/gr-osmosdr-mimo-txcount-fixed/lib/python3.12/site-packages:$PYTHONPATH
  export LD_LIBRARY_PATH=$HOME/opt/gr-osmosdr-mimo-txcount-fixed/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
  python3 H194E_BPSK_TX_V18Z38_MIMO_QKD.py --seconds 90 --frames 256 --gain 14
Receiver (RECEIVER_BOB folder; NEVER reuse a tag):
  python3 H194E_V18Z34_CAPTURE.py --state ON --tag DEMO1 --seconds 13
  python3 H194E_V18Z38_QKD_ANALYZE.py --rx0 H194E_V18Z34_DEMO1_ON_RX0.c64 --rx1 H194E_V18Z34_DEMO1_ON_RX1.c64
Antennas: Sender TX1/TX2, Receiver RX1/RX2, other ports 50 ohm, 16.4 cm spacing, 2 m.

## Suggested demo order (about 10 minutes)
1) DEMO 1 clean, Eve, loss  2) DEMO 2  3) DEMO 3  4) DEMO 4  5) optional live transmission on the Desktop PCs.
