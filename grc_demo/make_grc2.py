"""More flowgraphs: replay of a stored capture (Demo 4), stored sweep table (Demo 3), UDP public channel (Demo 1), live Receiver/Sender."""
import json, os
from make_grc import *   # FG, Q, SRC_CODE, ...

DEC2 = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.QubitDecoder):
    """Receiver: sync, channel estimate, MMSE or ZF, random-basis measurement, sifting, QBER, Cascade, privacy amplification."""
    def __init__(self, seed=20261030, receiver_seed=777, batch_frames=40, key_frames=200, skip_first=0, reset=0, detector="MMSE"):
        qkd_grc.QubitDecoder.__init__(self, seed, receiver_seed, batch_frames, key_frames, skip_first, reset, detector)
'''
DEC_LIVE = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.QubitDecoder):
    """Live Receiver: sync, channel estimate, MMSE or ZF, random-basis measurement, sifting, QBER, Cascade, privacy amplification. Decodes in a background thread so the radio stream is never blocked."""
    def __init__(self, seed=20261030, receiver_seed=777, batch_frames=40, key_frames=200, skip_first=0, reset=0, detector="MMSE", threaded=1):
        qkd_grc.QubitDecoder.__init__(self, seed, receiver_seed, batch_frames, key_frames, skip_first, reset, detector, False, threaded)
'''
UDP_CODE = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.UdpRunner):
    """Public channel over UDP: BB84 sifting, test subset, verdict and reconciliation traffic between two computers."""
    def __init__(self, role="sender", peer="127.0.0.1:5005", listen=5006, n=40000, qch=0.02, q_eve=0.0, p_loss=0.0, go=0):
        qkd_grc.UdpRunner.__init__(self, role, peer, listen, n, qch, q_eve, p_loss, go)
'''
TABLE_CODE = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.ResultsTable):
    """Stored fresh-sweep results (W1/W2): pick a capture, read its numbers."""
    def __init__(self, idx=0, table="w1w2_table.json"):
        qkd_grc.ResultsTable.__init__(self, idx, table)
'''
REPLAY_CODE = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.CaptureReplay):
    """Plays two stored capture files (RX0, RX1) in a loop; a missing file only prints a message."""
    def __init__(self, rx0_file="H194E_V18Z34_SWW203_ON_RX0.c64", rx1_file="H194E_V18Z34_SWW203_ON_RX1.c64"):
        qkd_grc.CaptureReplay.__init__(self, rx0_file, rx1_file)
'''
PLAYER_CODE = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.BladeRFPlayer):
    """Sender laptop: loops `bash ~/txfiles/tx.sh GAIN` (bladeRF-cli plays the stored 2x2 waveform) while run = 1."""
    def __init__(self, gain=30, run=0, script="~/txfiles/tx.sh"):
        qkd_grc.BladeRFPlayer.__init__(self, gain, run, script)
'''


def rx_displays(f, src0, src1, dec="receiver", row0=4):
    """Common receiver GUI: qubit plane, result numbers, receive scope and spectrum."""
    f.add("blocks_complex_to_real", "re_r0", vlen="1"); f.add("blocks_complex_to_real", "re_r1", vlen="1")
    f.add("qtgui_time_sink_x", "rx_scope", type="float", name=Q("Receiver antennas RX0 / RX1 (frames: pilots, index, qubits, guard)"),
          size="96000", srate="samp_rate", nconnections="2", update_time="0.5", autoscale="True", gui_hint=f"{row0+3},0,2,4",
          label1=Q("RX0"), label2=Q("RX1"))
    f.add("qtgui_const_sink_x", "qubit_plane", type="complex",
          name=Q("Receiver's qubit plane (z1, z2): the four BB84 states (1,0) (0,1) (0.7,0.7) (0.7,-0.7)"),
          size="1088", nconnections="1", update_time="0.2", autoscale="False", ymin="-2", ymax="2", xmin="-2", xmax="2",
          gui_hint=f"{row0},0,3,2")
    f.add("qtgui_number_sink", "readout", type="float", name=Q("Result"), nconnections="7", avg="0",
          graph_type="qtgui.NUM_GRAPH_NONE", update_time="0.3", autoscale="False", min="0", max="100", gui_hint=f"{row0},2,3,2",
          label1=Q("QBER"), unit1=Q("%"), label2=Q("Q_upper (abort if > 11)"), unit2=Q("%"),
          label3=Q("SINR stream A"), unit3=Q("dB"), label4=Q("SINR stream B"), unit4=Q("dB"),
          label5=Q("Secret key"), unit5=Q("bits"), label6=Q("Frames decoded"), unit6=Q(""),
          label7=Q("Status (0 busy, 1 key, 2 abort)"), unit7=Q(""))
    f.conn(src0[0], src0[1], "re_r0", 0); f.conn(src1[0], src1[1], "re_r1", 0)
    f.conn("re_r0", 0, "rx_scope", 0); f.conn("re_r1", 0, "rx_scope", 1)
    f.conn(dec, 0, "qubit_plane", 0)
    for k in range(7):
        f.conn(dec, 1 + k, "readout", k)


def build_replay():
    f = FG("demo_4_replay", "Decode a stored REAL 2x2 radio capture")
    f.add("variable", "samp_rate", value="2000000")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Plays a recorded capture of the real radio link (two files) through the Receiver. Put the .c64 files in this folder."), gui_hint="0,0,1,4")
    f.add("variable_qtgui_entry", "rx0_file", label=Q("RX0 file"), type="string", value=Q("H194E_V18Z34_SWW203_ON_RX0.c64"), gui_hint="1,0,1,2")
    f.add("variable_qtgui_entry", "rx1_file", label=Q("RX1 file"), type="string", value=Q("H194E_V18Z34_SWW203_ON_RX1.c64"), gui_hint="1,2,1,2")
    f.add("variable_qtgui_chooser", "det", label=Q("Detector"), type="string", value=Q("MMSE"), num_opts="2", option0=Q("MMSE"), option1=Q("ZF"),
          label0=Q("MMSE"), label1=Q("ZF (zero forcing)"), widget="combo_box", gui_hint="2,0,1,2")
    f.add("variable_qtgui_push_button", "reset", label=Q("New session"), type="int", value="0", pressed="1", released="0", gui_hint="2,2,1,2")
    f.add("epy_block", "receiver", code=DEC2, seed="20261030", receiver_seed="777", batch_frames="40", key_frames="250", skip_first="200000",
          reset="reset", detector="det")
    f.add("epy_block", "replay", code=REPLAY_CODE, rx0_file="rx0_file", rx1_file="rx1_file")
    f.conn("replay", 0, "receiver", 0); f.conn("replay", 1, "receiver", 1)
    rx_displays(f, ("replay", 0), ("replay", 1))
    f.save("demo_4_replay.grc")


def build_table():
    d = json.load(open(os.path.join(HERE, "w1w2_table.json")))
    rows = [(k, r) for k in d for r in d[k]]
    f = FG("demo_3_sweep_table", "Fresh-sweep results (W1 / W2)", size="(900,520)")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Pick a stored capture: transmit gain, SINR, QBER and key length with the MMSE and ZF detectors."), gui_hint="0,0,1,2")
    n = len(rows)
    f.add("variable_qtgui_range", "which", label=Q("Capture number (0 to %d; 0-16 = W1, 17-30 = W2)" % (n - 1)), rangeType="int", value="0", start="0", stop=str(n - 1), step="1",
          widget="counter_slider", gui_hint="1,0,1,2")
    f.add("epy_block", "table", code=TABLE_CODE, idx="which", table=Q("w1w2_table.json"))
    f.add("qtgui_number_sink", "readout", type="float", name=Q("Stored result"), nconnections="7", avg="0", graph_type="qtgui.NUM_GRAPH_NONE",
          update_time="0.3", autoscale="False", min="0", max="100", gui_hint="2,0,3,2",
          label1=Q("Capture tag (SWW...)"), unit1=Q(""), label2=Q("TX gain"), unit2=Q("dB"), label3=Q("SINR"), unit3=Q("dB"),
          label4=Q("QBER (MMSE)"), unit4=Q("%"), label5=Q("QBER (ZF)"), unit5=Q("%"), label6=Q("Key (MMSE)"), unit6=Q("bits"),
          label7=Q("Key (ZF)"), unit7=Q("bits"))
    for k in range(7):
        f.conn("table", k, "readout", k)
    f.save("demo_3_sweep_table.grc")
    print(len(rows), "stored captures in W1/W2 (chooser shows the first", min(n, 20), ")")


def build_udp():
    f = FG("demo_1_udp", "Public channel over UDP (run on both laptops)", size="(900,650)")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Run this on BOTH laptops: one Sender, one Receiver. Start the Receiver first, then press Start on both."), gui_hint="0,0,1,4")
    f.add("variable_qtgui_chooser", "role", label=Q("This laptop is"), type="string", value=Q("receiver"), num_opts="2",
          option0=Q("receiver"), option1=Q("sender"), label0=Q("Receiver"), label1=Q("Sender"), widget="combo_box", gui_hint="1,0,1,2")
    f.add("variable_qtgui_entry", "peer", label=Q("Other laptop IP:port"), type="string", value=Q("127.0.0.1:5006"), gui_hint="1,2,1,2")
    f.add("variable_qtgui_range", "q_eve", label=Q("Eavesdropper: share of qubits intercepted"), value="0", start="0", stop="1", step="0.25",
          widget="counter_slider", gui_hint="2,0,1,2")
    f.add("variable_qtgui_range", "p_loss", label=Q("Frame loss (Receiver side)"), value="0", start="0", stop="0.3", step="0.01",
          widget="counter_slider", gui_hint="2,2,1,2")
    f.add("variable_qtgui_range", "qch", label=Q("Channel disturbance (QBER)"), value="0.02", start="0", stop="0.2", step="0.01",
          widget="counter_slider", gui_hint="3,0,1,2")
    f.add("variable_qtgui_push_button", "go", label=Q("Start"), type="int", value="0", pressed="1", released="0", gui_hint="3,2,1,2")
    f.add("epy_block", "udp", code=UDP_CODE, role="role", peer="peer", listen="5005 if role == 'receiver' else 5006", n="40000",
          qch="qch", q_eve="q_eve", p_loss="p_loss", go="go")
    f.add("qtgui_number_sink", "readout", type="float", name=Q("Result (same on both laptops when no abort)"), nconnections="5", avg="0",
          graph_type="qtgui.NUM_GRAPH_NONE", update_time="0.3", autoscale="False", min="0", max="100", gui_hint="4,0,3,4",
          label1=Q("Estimated QBER"), unit1=Q("%"), label2=Q("Secret key"), unit2=Q("bits"), label3=Q("Frames sent"), unit3=Q(""),
          label4=Q("Frames lost / resent"), unit4=Q(""), label5=Q("Status (1 running, 2 key, 3 abort)"), unit5=Q(""))
    for k in range(5):
        f.conn("udp", k, "readout", k)
    f.save("demo_1_udp.grc")


def build_live_rx():
    f = FG("demo_5_live_receiver", "LIVE 2x2 radio: Receiver (bladeRF RX0 + RX1)")
    f.add("variable", "samp_rate", value="2000000")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Radios warmed up ~20 min. Start the Sender first. This window then decodes the live link frame by frame."), gui_hint="0,0,1,4")
    f.add("variable_qtgui_range", "gain0", label=Q("RX0 gain (dB)"), value="20", start="0", stop="60", step="1", widget="counter_slider", gui_hint="1,0,1,2")
    f.add("variable_qtgui_range", "gain1", label=Q("RX1 gain (dB)"), value="30", start="0", stop="60", step="1", widget="counter_slider", gui_hint="1,2,1,2")
    f.add("variable_qtgui_push_button", "reset", label=Q("New session"), type="int", value="0", pressed="1", released="0", gui_hint="2,0,1,4")
    f.add("epy_block", "receiver", code=DEC_LIVE, seed="20261030", receiver_seed="777", batch_frames="40", key_frames="200", skip_first="200000",
          reset="reset", detector=Q("MMSE"), threaded="1")
    f.add("osmosdr_source", "radio", type="fc32", args=Q("numchan=2 bladerf=0,nchan=2"), nchan="2", sample_rate="samp_rate",
          freq0="915000000", gain_mode0="False", gain0="gain0", bw0="1000000", freq1="915000000", gain_mode1="False", gain1="gain1", bw1="1000000")
    f.conn("radio", 0, "receiver", 0); f.conn("radio", 1, "receiver", 1)
    rx_displays(f, ("radio", 0), ("radio", 1))
    f.save("demo_5_live_receiver.grc")


def build_live_tx():
    f = FG("demo_5_live_sender", "LIVE 2x2 radio: Sender (laptop, bladeRF-cli)", size="(700,420)")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Sender laptop: press Start to loop the stored 2x2 waveform (each run is 50 s). Press again to stop after the current run."), gui_hint="0,0,1,2")
    f.add("variable_qtgui_range", "gain", label=Q("Transmit gain (dB)"), rangeType="int", value="30", start="0", stop="60", step="1",
          widget="counter_slider", gui_hint="1,0,1,2")
    f.add("variable_qtgui_toggle_switch", "run", label=Q("Transmit"), type="int", value="0", pressed="1", released="0", gui_hint="2,0,1,2") if False else None
    f.add("variable_qtgui_push_button", "run", label=Q("Start / stop transmit"), type="int", value="0", pressed="1", released="0", gui_hint="2,0,1,2") if False else None
    f.add("variable_qtgui_check_box", "tx_on", label=Q("Transmit"), type="int", value="0", true="1", false="0", gui_hint="2,0,1,2")
    f.add("epy_block", "player", code=PLAYER_CODE, gain="gain", run="tx_on", script=Q("~/txfiles/tx.sh"))
    f.add("qtgui_number_sink", "readout", type="float", name=Q("Sender"), nconnections="3", avg="0", graph_type="qtgui.NUM_GRAPH_NONE",
          update_time="0.3", autoscale="False", min="0", max="100", gui_hint="3,0,2,2",
          label1=Q("Runs finished"), unit1=Q(""), label2=Q("Runs cut short (USB drop)"), unit2=Q(""), label3=Q("Transmitting (1 = yes)"), unit3=Q(""))
    for k in range(3):
        f.conn("player", k, "readout", k)
    f.save("demo_5_live_sender.grc")


if __name__ == "__main__":
    import sys
    for w in sys.argv[1:] or ["replay", "table", "udp", "rx", "tx"]:
        dict(replay=build_replay, table=build_table, udp=build_udp, rx=build_live_rx, tx=build_live_tx)[w]()
