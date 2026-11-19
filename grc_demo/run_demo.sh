#!/bin/bash
# Usage: bash run_demo.sh 1|2|3|4|5r|5rl|5s|6|6r|6rl|6s     (runs the generated Python of the flowgraph; no GRC editor needed)
cd "$(dirname "$0")"
case "$1" in
  1)  f=demo_1_udp ;;
  2)  f=demo_2_sim_radio ;;
  3)  f=demo_3_sweep_table ;;
  4)  f=demo_4_replay ;;
  5r) f=demo_5_live_receiver ;;
  5rl) f=demo_5_live_receiver_lab ;;
  5s) f=demo_5_live_sender ;;
  6)  f=demo_6_message_sim ;;
  6r) f=demo_6_message_receiver ;;
  6rl) f=demo_6_message_receiver_lab ;;
  6s) f=demo_6_message_sender ;;
  *)  echo "usage: bash run_demo.sh 1|2|3|4|5r|5rl|5s|6|6r|6rl|6s"; exit 1 ;;
esac
python3 -u $f.py
