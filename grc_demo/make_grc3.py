"""Demo 6 flowgraphs: send a text message over the spatial-qubit link (simulation; live Receiver)."""
from make_grc import *   # FG, Q, ...

_HDR = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc
'''
MSG_SRC = _HDR + '''
class blk(qkd_grc.MessageSource):
    """Sender: splits the text into 30-byte chunks (+CRC32), one chunk per 48 ms frame, Z basis (bit 0 on TX1, bit 1 on TX2), and repeats the message in a loop."""
    def __init__(self, text="hello", amplitude=0.14, send=0):
        qkd_grc.MessageSource.__init__(self, text, amplitude, send)
'''
MSG_DEC = _HDR + '''
class blk(qkd_grc.MessageDecoder):
    """Receiver: pilot sync, channel estimate, MMSE, then CRC check per chunk; the first good copy of every chunk is kept and the text is assembled."""
    def __init__(self, batch_frames=3, skip_first=0, reset=0, detector="MMSE", threaded=0):
        qkd_grc.MessageDecoder.__init__(self, batch_frames, skip_first, reset, detector, False, threaded)
'''
SNIP = '''from PyQt5 import Qt
_lab = Qt.QLabel("(waiting for a message)")
_lab.setWordWrap(True)
_lab.setAlignment(Qt.Qt.AlignCenter)
_lab.setMinimumHeight(70)
_lab.setStyleSheet("font-size: 22px; font-weight: bold; padding: 8px; border: 2px solid #888; border-radius: 6px;")
self.top_grid_layout.addWidget(_lab, ROW, 0, 1, 4)
def _upd():
    d = self.receiver
    st = int(d.vals[4])
    txt = d.shown if st == 2 else ("receiving: %d good chunk(s) so far ..." % int(d.vals[1]) if st == 1 else "(waiting for a message)")
    _lab.setText("Received: " + txt if st == 2 else txt)
    _lab.setStyleSheet("font-size: 22px; font-weight: bold; padding: 8px; border-radius: 6px; border: 2px solid %s;" % ("#2a9d3a" if st == 2 else "#c88a00" if st == 1 else "#888"))
try:                                  # "Send again" also takes the text typed in the box (no Enter needed)
    _le = self._msg_line_edit
    for _b in self.findChildren(Qt.QPushButton):
        if _b.text() == "Send again":
            _b.pressed.connect(lambda: self.set_msg(str(_le.text())))
except Exception as _e:
    print("note: could not link the Send button to the message box:", _e)
_tm = Qt.QTimer()
_tm.timeout.connect(_upd)
_tm.start(250)
self._msg_timer = _tm
'''
LABELS = dict(label1=Q("Frames synchronised"), unit1=Q(""), label2=Q("Good chunks (CRC ok)"), unit2=Q(""),
              label3=Q("Bad-CRC copies"), unit3=Q(""), label4=Q("Message length"), unit4=Q("bytes"),
              label5=Q("Status (0 wait, 1 receiving, 2 received)"), unit5=Q(""),
              label6=Q("Time since Sender started it (simulation)"), unit6=Q("s"), label7=Q("SINR (mean of A, B)"), unit7=Q("dB"))


def common_rx(f, s0, s1, row0):
    f.add("snippet", "show_text", section="main_after_init", priority="0", code=SNIP.replace("ROW", str(row0)))
    f.add("blocks_complex_to_real", "re_r0", vlen="1"); f.add("blocks_complex_to_real", "re_r1", vlen="1")
    f.add("qtgui_const_sink_x", "qubit_plane", type="complex", name=Q("Receiver's qubit plane: two clusters = bit 0 (1,0) and bit 1 (0,1)"),
          size="1088", nconnections="1", update_time="0.2", autoscale="False", ymin="-2", ymax="2", xmin="-2", xmax="2",
          gui_hint=f"{row0+1},0,3,2")
    f.add("qtgui_number_sink", "readout", type="float", name=Q("Message receive status"), nconnections="7", avg="0",
          graph_type="qtgui.NUM_GRAPH_NONE", update_time="0.3", autoscale="False", min="0", max="100",
          gui_hint=f"{row0+1},2,3,2", **LABELS)
    f.add("qtgui_time_sink_x", "rx_scope", type="float", name=Q("Receiver antennas RX0 / RX1"),
          size="96000", srate="samp_rate", nconnections="2", update_time="0.5", autoscale="True",
          gui_hint=f"{row0+4},0,2,4", label1=Q("RX0"), label2=Q("RX1"))
    f.conn(*s0, "re_r0", 0); f.conn(*s1, "re_r1", 0)
    f.conn("re_r0", 0, "rx_scope", 0); f.conn("re_r1", 0, "rx_scope", 1)
    f.conn("receiver", 0, "qubit_plane", 0)
    for k in range(7):
        f.conn("receiver", 1 + k, "readout", k)


def build_msg_sim():
    f = FG("demo_6_message_sim", "Send a text message over the simulated 2x2 radio")
    f.add("variable", "samp_rate", value="2000000")
    f.add("import", "imp_np", imports="import numpy as np")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Type a message, press Enter. Sender: 30-byte chunks + CRC per 48 ms frame -> 2x2 channel + noise -> Receiver checks every CRC and rebuilds the text."),
          gui_hint="0,0,1,4")
    f.add("variable_qtgui_entry", "msg", label=Q("Message to send (max 240 bytes)"), type="string", value=Q("hello"), gui_hint="1,0,1,3")
    f.add("variable_qtgui_push_button", "send", label=Q("Send again"), type="int", value="0", pressed="1", released="0", gui_hint="1,3,1,1")
    f.add("variable_qtgui_range", "noise", label=Q("Receiver noise level"), value="0.1", start="0", stop="1.0", step="0.02",
          widget="counter_slider", gui_hint="2,0,1,2")
    f.add("variable_qtgui_range", "cfo", label=Q("Carrier offset between radios (Hz)"), value="500", start="-2000", stop="2000", step="50",
          widget="counter_slider", gui_hint="2,2,1,2")
    f.add("variable_qtgui_range", "mix", label=Q("Cross-talk between the two antennas"), value="0.35", start="0", stop="0.9", step="0.05",
          widget="counter_slider", gui_hint="3,0,1,2")
    f.add("variable_qtgui_range", "phase", label=Q("Cross-talk phase (deg)"), value="40", start="0", stop="180", step="5",
          widget="counter_slider", gui_hint="3,2,1,2")
    f.add("variable_qtgui_push_button", "reset", label=Q("Clear receiver"), type="int", value="0", pressed="1", released="0", gui_hint="1,4,1,1")
    f.add("variable", "h01", value="mix*np.exp(1j*np.deg2rad(phase))")
    f.add("variable", "h10", value="0.85*mix*np.exp(1j*np.deg2rad(phase+70))")
    f.add("variable", "h11", value="0.9*np.exp(0.7j)")
    f.add("epy_block", "sender", code=MSG_SRC, text="msg", amplitude="0.14", send="send")
    f.add("epy_block", "receiver", code=MSG_DEC, batch_frames="3", skip_first="0", reset="reset", detector=Q("MMSE"), threaded="0")
    for i in "01":
        f.add("blocks_throttle", f"thr{i}", type="complex", samples_per_second="samp_rate", vlen="1", ignoretag="True")
    for nm, c in (("g00", "1"), ("g01", "h01"), ("g10", "h10"), ("g11", "h11")):
        f.add("blocks_multiply_const_vxx", nm, type="complex", const=c, vlen="1")
    for nm in ("sum0", "sum1", "rx0", "rx1"):
        f.add("blocks_add_xx", nm, type="complex", num_inputs="2", vlen="1")
    f.add("analog_noise_source_x", "n0", type="complex", noise_type="analog.GR_GAUSSIAN", amp="noise", seed="1")
    f.add("analog_noise_source_x", "n1", type="complex", noise_type="analog.GR_GAUSSIAN", amp="noise", seed="2")
    f.add("analog_sig_source_x", "lo", type="complex", samp_rate="samp_rate", waveform="analog.GR_COS_WAVE", freq="cfo",
          amp="1", offset="0", phase="0")
    f.add("blocks_multiply_xx", "cfo0", type="complex", num_inputs="2", vlen="1")
    f.add("blocks_multiply_xx", "cfo1", type="complex", num_inputs="2", vlen="1")
    f.conn("sender", 0, "thr0", 0); f.conn("sender", 1, "thr1", 0)
    f.conn("thr0", 0, "g00", 0); f.conn("thr1", 0, "g01", 0); f.conn("thr0", 0, "g10", 0); f.conn("thr1", 0, "g11", 0)
    f.conn("g00", 0, "sum0", 0); f.conn("g01", 0, "sum0", 1); f.conn("g10", 0, "sum1", 0); f.conn("g11", 0, "sum1", 1)
    f.conn("sum0", 0, "rx0", 0); f.conn("n0", 0, "rx0", 1); f.conn("sum1", 0, "rx1", 0); f.conn("n1", 0, "rx1", 1)
    f.conn("rx0", 0, "cfo0", 0); f.conn("lo", 0, "cfo0", 1); f.conn("rx1", 0, "cfo1", 0); f.conn("lo", 0, "cfo1", 1)
    f.conn("cfo0", 0, "receiver", 0); f.conn("cfo1", 0, "receiver", 1)
    common_rx(f, ("cfo0", 0), ("cfo1", 0), 4)
    f.save("demo_6_message_sim.grc")


MSG_PLAY = _HDR + '''
class blk(qkd_grc.MessagePlayer):
    """Sender laptop: builds the message waveform, writes ~/txfiles/MSG_AB.bin (same format as TX_AB.bin) and plays it with bladeRF-cli for 30 s."""
    def __init__(self, text="hello", gain=30, send=0):
        qkd_grc.MessagePlayer.__init__(self, text, gain, send)
'''
SNIP_TX = '''from PyQt5 import Qt
try:                                  # "Send message" takes the text typed in the box (no Enter needed)
    _le = self._msg_line_edit
    for _b in self.findChildren(Qt.QPushButton):
        if _b.text() == "Send message":
            _b.pressed.connect(lambda: self.set_msg(str(_le.text())))
except Exception as _e:
    print("note: could not link the Send button to the message box:", _e)
'''


def build_msg_tx():
    f = FG("demo_6_message_sender", "LIVE 2x2 radio: message Sender (laptop, bladeRF-cli)", size="(800,420)")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Type a message, set the gain, press Send message. Radios warmed up; start the message Receiver first. One transmission lasts 30 s and repeats the message."),
          gui_hint="0,0,1,2")
    f.add("variable_qtgui_entry", "msg", label=Q("Message to send (max 240 bytes)"), type="string", value=Q("hello"), gui_hint="1,0,1,2")
    f.add("variable_qtgui_range", "gain", label=Q("Transmit gain (dB)"), rangeType="int", value="30", start="0", stop="60", step="1",
          widget="counter_slider", gui_hint="2,0,1,2")
    f.add("variable_qtgui_push_button", "send", label=Q("Send message"), type="int", value="0", pressed="1", released="0", gui_hint="3,0,1,2")
    f.add("epy_block", "player", code=MSG_PLAY, text="msg", gain="gain", send="send")
    f.add("snippet", "link_send", section="main_after_init", priority="0", code=SNIP_TX)
    f.add("qtgui_number_sink", "readout", type="float", name=Q("Message Sender"), nconnections="5", avg="0", graph_type="qtgui.NUM_GRAPH_NONE",
          update_time="0.3", autoscale="False", min="0", max="100", gui_hint="4,0,2,2",
          label1=Q("Transmissions finished"), unit1=Q(""), label2=Q("Failed (USB drop)"), unit2=Q(""),
          label3=Q("Status (0 idle, 1 preparing, 2 transmitting)"), unit3=Q(""), label4=Q("Chunks in message"), unit4=Q(""),
          label5=Q("Message loop"), unit5=Q("s"))
    for k in range(5):
        f.conn("player", k, "readout", k)
    f.save("demo_6_message_sender.grc")


def build_msg_rx():
    f = FG("demo_6_message_receiver", "LIVE 2x2 radio: message Receiver (bladeRF RX0 + RX1)")
    f.add("variable", "samp_rate", value="2000000")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Radios warmed up ~20 min. Start this window, then start the message Sender. The text appears below when every chunk has a valid CRC."),
          gui_hint="0,0,1,4")
    f.add("variable_qtgui_range", "gain0", label=Q("RX0 gain (dB)"), value="20", start="0", stop="60", step="1", widget="counter_slider", gui_hint="1,0,1,2")
    f.add("variable_qtgui_range", "gain1", label=Q("RX1 gain (dB)"), value="30", start="0", stop="60", step="1", widget="counter_slider", gui_hint="1,2,1,2")
    f.add("variable_qtgui_push_button", "reset", label=Q("Clear receiver"), type="int", value="0", pressed="1", released="0", gui_hint="2,0,1,4")
    f.add("epy_block", "receiver", code=MSG_DEC, batch_frames="3", skip_first="200000", reset="reset", detector=Q("MMSE"), threaded="1")
    f.add("osmosdr_source", "radio", type="fc32", args=Q("numchan=2 bladerf=0,nchan=2"), nchan="2", sample_rate="samp_rate",
          freq0="915000000", gain_mode0="False", gain0="gain0", bw0="1000000", freq1="915000000", gain_mode1="False", gain1="gain1", bw1="1000000")
    f.conn("radio", 0, "receiver", 0); f.conn("radio", 1, "receiver", 1)
    common_rx(f, ("radio", 0), ("radio", 1), 3)
    f.save("demo_6_message_receiver.grc")


if __name__ == "__main__":
    import sys
    for w in sys.argv[1:] or ["sim", "rx", "tx"]:
        dict(sim=build_msg_sim, rx=build_msg_rx, tx=build_msg_tx)[w]()
