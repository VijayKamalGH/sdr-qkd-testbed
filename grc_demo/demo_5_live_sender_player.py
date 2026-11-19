import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.BladeRFPlayer):
    """Sender laptop: loops `bash ~/txfiles/tx.sh GAIN` (bladeRF-cli plays the stored 2x2 waveform) while run = 1."""
    def __init__(self, gain=30, run=0, script="~/txfiles/tx.sh"):
        qkd_grc.BladeRFPlayer.__init__(self, gain, run, script)
