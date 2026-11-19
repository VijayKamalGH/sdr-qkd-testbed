# GNU Radio Companion demos -- SDR 2x2 MIMO spatial-qubit BB84

Files: `demo_*.grc` (open in GNU Radio Companion), `demo_*.py` (the same flowgraphs already generated; run without the editor),
`qkd_grc.py` (the Sender / Receiver / helper blocks), `H194E_*.py` (FROZEN lab files, unchanged), `w1w2_table.json`.
Generated and tested with GNU Radio 3.10.9.2 / Python 3.12. The lab laptops have GNU Radio 3.10.5.1 / Python 3.10: open each .grc once and press
Generate (or Run) so it is rebuilt for that version.

Run from THIS folder (the blocks find qkd_grc.py in the working directory):
    cd grc_demo
    gnuradio-companion demo_2_sim_radio.grc        # edit, then press Run
    bash run_demo.sh 2                              # or run without the editor

| Demo | File | Radio needed | What to do |
|---|---|---|---|
| 1 UDP public channel | demo_1_udp | no (2 laptops) | Receiver laptop: role Receiver, peer = SENDER_IP:5006; Sender laptop: role Sender, peer = RECEIVER_IP:5005. Press Start on the Receiver, then on the Sender. Sliders: Eve, frame loss. |
| 2 Simulated radio | demo_2_sim_radio | no (1 laptop) | Run. Move Eve / noise / cross-talk sliders, press "New session", watch QBER, key, qubit plane. |
| 3 Sweep table | demo_3_sweep_table | no | Move the capture slider (0-16 W1, 17-30 W2). |
| 4 Real-capture replay | demo_4_replay | no | Put H194E_V18Z34_SWW203_ON_RX0.c64 / _RX1.c64 in this folder, run. Choose MMSE or ZF. |
| 5 Live Receiver | demo_5_live_receiver | yes, Receiver laptop | Radios warmed up ~20 min. Start the Sender first. |
| 5 Live Sender | demo_5_live_sender | yes, Sender laptop | Needs ~/txfiles/tx.sh and TX_AB.bin. Tick "Transmit". |
| 6 Message, simulated | demo_6_message_sim | no (1 laptop) | Run, type a text (max 240 bytes) in the entry box, press Enter. "Send again" repeats it. The green box shows the text once every 30-byte chunk has a valid CRC. Sliders: noise, carrier offset, cross-talk. |
| 6 Message, live Receiver | demo_6_message_receiver (or `_lab.py`) | yes, Receiver laptop | Same radio setup as Demo 5 (lab variant `bash run_demo.sh 6rl`). Start it, then start the message Sender. |
| 6 Message, live Sender | demo_6_message_sender (`bash run_demo.sh 6s`) | yes, Sender laptop | Type the text, set gain, press Send message. Writes ~/txfiles/MSG_AB.bin (same int16 format as TX_AB.bin, scale taken from the lab files) and plays it with bladeRF-cli for 30 s. Prints start/end wall-clock times; the Receiver prints the time the message was complete. |

Message framing (Demo 6, same as the frozen H194E_R1_RADIO_PIPE.py): b"R1" + msgid(2 bytes) + length(4 bytes) + text, in 30-byte chunks, each with a CRC32;
one chunk per 48 ms frame, Z basis only (bit 0 on TX1, bit 1 on TX2); the Sender loops the message, the Receiver keeps the first CRC-valid copy of each chunk.
The "time since the Sender started it" readout exists only in the simulation (one clock). Between two computers a one-way delay cannot be measured:
the clocks are independent. What can be stated: 48 ms of airtime per chunk, propagation about 7 ns per 2 m.
