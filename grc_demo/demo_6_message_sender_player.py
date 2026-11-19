import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.MessagePlayer):
    """Sender laptop: builds the message waveform, writes ~/txfiles/MSG_AB.bin (same format as TX_AB.bin) and plays it with bladeRF-cli for 30 s."""
    def __init__(self, text="hello", gain=30, send=0):
        qkd_grc.MessagePlayer.__init__(self, text, gain, send)
