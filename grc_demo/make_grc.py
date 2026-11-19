"""Generates the .grc flowgraphs of the demo with GNU Radio's own GRC API (so the files are schema-correct).
Run:  python3.12 make_grc.py      (writes demo_*.grc next to this file)"""
import os, sys
from gnuradio import gr
from gnuradio.grc.core.platform import Platform

HERE = os.path.dirname(os.path.abspath(__file__))
P = Platform(version=gr.version(), version_parts=(gr.major_version(), gr.api_version(), gr.minor_version()),
             prefs=gr.prefs())
P.build_library()

# Code placed inside each embedded Python block (GRC reads __init__ arguments as block parameters).
SRC_CODE = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.QubitSource):
    """Sender: builds the frozen frame (pilots, index word, 272 spatial qubits) on TX1/TX2. eve_rate = share of qubits an eavesdropper intercepts."""
    def __init__(self, seed=20261030, amplitude=0.14, eve_rate=0.0):
        qkd_grc.QubitSource.__init__(self, seed, amplitude, eve_rate)
'''

DEC_CODE = '''import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.QubitDecoder):
    """Receiver: sync, channel estimate, MMSE, random-basis measurement, sifting, QBER, Cascade, privacy amplification."""
    def __init__(self, seed=20261030, receiver_seed=777, batch_frames=40, key_frames=200, skip_first=0, reset=0):
        qkd_grc.QubitDecoder.__init__(self, seed, receiver_seed, batch_frames, key_frames, skip_first, reset)
'''


class FG:
    def __init__(self, fid, title, size="(1250,950)"):
        self.fg = P.make_flow_graph()
        o = self.fg.options_block
        for k, v in dict(id=fid, title=title, author="", generate_options="qt_gui", run_options="prompt",
                         window_size=size, catch_exceptions="True").items():
            o.params[k].set_value(v)
        self.ids = {}

    def add(self, bid, _id, **params):
        b = self.fg.new_block(bid)
        assert b is not None, bid
        b.params["id"].set_value(_id)
        if bid == "epy_block":
            b.params["_source_code"].set_value(params.pop("code"))
            b.rewrite(); b.params["id"].set_value(_id)
        for k, v in params.items():
            b.params[k].set_value(str(v))
        b.rewrite()
        self.ids[_id] = b
        return b

    def conn(self, a, pa, b, pb):
        sa = self.ids[a].get_source(str(pa)); sb = self.ids[b].get_sink(str(pb))
        self.fg.connect(sa, sb)

    def save(self, name):
        self.fg.rewrite(); self.fg.validate()
        bad = [(b.name, [str(e) for e in b.get_error_messages()]) for b in self.fg.blocks if not b.is_valid()]
        if bad:
            print("INVALID in", name, bad)
        P.save_flow_graph(os.path.join(HERE, name), self.fg)
        print("wrote", name)


Q = lambda s: '"' + s + '"'


def build_sim():
    f = FG("demo_2_sim_radio", "Spatial-qubit BB84 over a simulated 2x2 radio")
    f.add("variable", "samp_rate", value="2000000")
    f.add("import", "imp_np", imports="import numpy as np")
    f.add("variable_qtgui_label", "howto", label=Q("How it works"), type="string", formatter="None",
          value=Q("Sender (TX1, TX2) -> 2x2 channel + noise -> Receiver. Move the sliders; press New session after each change."),
          gui_hint="0,0,1,4")
    f.add("variable_qtgui_range", "eve_rate", label=Q("Eavesdropper: share of qubits intercepted"), value="0", start="0", stop="1",
          step="0.05", widget="counter_slider", gui_hint="1,0,1,2")
    f.add("variable_qtgui_range", "noise", label=Q("Receiver noise level"), value="0.2", start="0", stop="1.5",
          step="0.02", widget="counter_slider", gui_hint="1,2,1,2")
    f.add("variable_qtgui_range", "mix", label=Q("Cross-talk between the two antennas"), value="0.35", start="0",
          stop="0.9", step="0.05", widget="counter_slider", gui_hint="2,0,1,2")
    f.add("variable_qtgui_range", "phase", label=Q("Cross-talk phase (deg)"), value="40", start="0", stop="180",
          step="5", widget="counter_slider", gui_hint="2,2,1,2")
    f.add("variable_qtgui_range", "cfo", label=Q("Carrier offset between radios (Hz)"), value="500", start="-2000",
          stop="2000", step="50", widget="counter_slider", gui_hint="3,0,1,2")
    f.add("variable_qtgui_push_button", "reset", label=Q("New session"), type="int", value="0", pressed="1", released="0",
          gui_hint="3,2,1,2")
    f.add("variable", "h00", value="1")
    f.add("variable", "h01", value="mix*np.exp(1j*np.deg2rad(phase))")
    f.add("variable", "h10", value="0.85*mix*np.exp(1j*np.deg2rad(phase+70))")
    f.add("variable", "h11", value="0.9*np.exp(0.7j)")
    f.add("epy_block", "sender", code=SRC_CODE, seed="20261030", amplitude="0.14", eve_rate="eve_rate")
    f.add("epy_block", "receiver", code=DEC_CODE, seed="20261030", receiver_seed="777", batch_frames="40", key_frames="200", skip_first="0", reset="reset")
    for i in "01":
        f.add("blocks_throttle", f"thr{i}", type="complex", samples_per_second="samp_rate", vlen="1", ignoretag="True")
    for nm, c in (("g00", "h00"), ("g01", "h01"), ("g10", "h10"), ("g11", "h11")):
        f.add("blocks_multiply_const_vxx", nm, type="complex", const=c, vlen="1")
    for nm in ("sum0", "sum1", "rx0", "rx1"):
        f.add("blocks_add_xx", nm, type="complex", num_inputs="2", vlen="1")
    f.add("analog_noise_source_x", "n0", type="complex", noise_type="analog.GR_GAUSSIAN", amp="noise", seed="1")
    f.add("analog_noise_source_x", "n1", type="complex", noise_type="analog.GR_GAUSSIAN", amp="noise", seed="2")
    f.add("analog_sig_source_x", "lo", type="complex", samp_rate="samp_rate", waveform="analog.GR_COS_WAVE", freq="cfo",
          amp="1", offset="0", phase="0")
    f.add("blocks_multiply_xx", "cfo0", type="complex", num_inputs="2", vlen="1")
    f.add("blocks_multiply_xx", "cfo1", type="complex", num_inputs="2", vlen="1")
    # displays
    f.add("blocks_complex_to_real", "re_a", vlen="1"); f.add("blocks_complex_to_real", "re_b", vlen="1")
    f.add("blocks_complex_to_real", "re_r0", vlen="1"); f.add("blocks_complex_to_real", "re_r1", vlen="1")
    f.add("qtgui_time_sink_x", "tx_scope", type="float", name=Q("Sender: one frame, TX1 (A) and TX2 (B)  [pilot A | pilot B | index | 272 qubits | guard]"),
          size="96000", srate="samp_rate", nconnections="2", update_time="0.5", autoscale="True", gui_hint="7,0,2,4",
          label1=Q("TX1 (stream A)"), label2=Q("TX2 (stream B)"))
    f.add("qtgui_time_sink_x", "rx_scope", type="float", name=Q("Receiver antennas RX0 / RX1 (after channel + noise)"),
          size="96000", srate="samp_rate", nconnections="2", update_time="0.5", autoscale="True", gui_hint="9,0,2,4",
          label1=Q("RX0"), label2=Q("RX1"))
    f.add("qtgui_const_sink_x", "qubit_plane", type="complex", name=Q("Receiver's qubit plane (z1, z2): the four BB84 states (1,0) (0,1) (0.7,0.7) (0.7,-0.7)"),
          size="1088", nconnections="1", update_time="0.2", autoscale="False", ymin="-2", ymax="2", xmin="-2", xmax="2",
          gui_hint="4,0,3,2")
    f.add("qtgui_number_sink", "readout", type="float", name=Q("Result"), nconnections="7", avg="0", graph_type="qtgui.NUM_GRAPH_NONE",
          update_time="0.3", autoscale="False", min="0", max="100", gui_hint="4,2,3,2",
          label1=Q("QBER"), unit1=Q("%"), label2=Q("Q_upper (abort if > 11)"), unit2=Q("%"),
          label3=Q("SINR stream A"), unit3=Q("dB"), label4=Q("SINR stream B"), unit4=Q("dB"),
          label5=Q("Secret key"), unit5=Q("bits"), label6=Q("Frames decoded"), unit6=Q(""),
          label7=Q("Status (0 busy, 1 key, 2 abort)"), unit7=Q(""))
    # wiring
    f.conn("sender", 0, "thr0", 0); f.conn("sender", 1, "thr1", 0)
    f.conn("thr0", 0, "g00", 0); f.conn("thr1", 0, "g01", 0); f.conn("thr0", 0, "g10", 0); f.conn("thr1", 0, "g11", 0)
    f.conn("g00", 0, "sum0", 0); f.conn("g01", 0, "sum0", 1); f.conn("g10", 0, "sum1", 0); f.conn("g11", 0, "sum1", 1)
    f.conn("sum0", 0, "rx0", 0); f.conn("n0", 0, "rx0", 1); f.conn("sum1", 0, "rx1", 0); f.conn("n1", 0, "rx1", 1)
    f.conn("rx0", 0, "cfo0", 0); f.conn("lo", 0, "cfo0", 1); f.conn("rx1", 0, "cfo1", 0); f.conn("lo", 0, "cfo1", 1)
    f.conn("cfo0", 0, "receiver", 0); f.conn("cfo1", 0, "receiver", 1)
    f.conn("thr0", 0, "re_a", 0); f.conn("thr1", 0, "re_b", 0); f.conn("re_a", 0, "tx_scope", 0); f.conn("re_b", 0, "tx_scope", 1)
    f.conn("cfo0", 0, "re_r0", 0); f.conn("cfo1", 0, "re_r1", 0); f.conn("re_r0", 0, "rx_scope", 0); f.conn("re_r1", 0, "rx_scope", 1)
    f.conn("receiver", 0, "qubit_plane", 0)
    for k in range(7):
        f.conn("receiver", 1 + k, "readout", k)
    f.save("demo_2_sim_radio.grc")


if __name__ == "__main__":
    which = sys.argv[1:] or ["sim"]
    if "sim" in which:
        build_sim()
