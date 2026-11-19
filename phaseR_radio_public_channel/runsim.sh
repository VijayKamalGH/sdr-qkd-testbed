#!/bin/bash
cd "$(dirname "$0")"
for P in bb84 bbm92; do
  rm -rf /tmp/r2sim
  python3 H194E_R2_RADIO_BB84.py --role receiver --mode sim --yes --lib simlib --listen 6011 --peer 127.0.0.1:6012 --frames 64 --protocol $P --sim-snr-f 14 > rcv_$P.log 2>&1 &
  python3 H194E_R2_RADIO_BB84.py --role sender --mode sim --yes --lib simlib --listen 6012 --peer 127.0.0.1:6011 --frames 64 --protocol $P --sim-snr-f 14 > snd_$P.log 2>&1
  wait
done
echo done > sim_done.txt
