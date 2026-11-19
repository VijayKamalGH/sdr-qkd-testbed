import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.MessageDecoder):
    """Receiver: pilot sync, channel estimate, MMSE, then CRC check per chunk; the first good copy of every chunk is kept and the text is assembled."""
    def __init__(self, batch_frames=3, skip_first=0, reset=0, detector="MMSE", threaded=0):
        qkd_grc.MessageDecoder.__init__(self, batch_frames, skip_first, reset, detector, False, threaded)
