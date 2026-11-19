import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.MessageSource):
    """Sender: splits the text into 30-byte chunks (+CRC32), one chunk per 48 ms frame, Z basis (bit 0 on TX1, bit 1 on TX2), and repeats the message in a loop."""
    def __init__(self, text="hello", amplitude=0.14, send=0):
        qkd_grc.MessageSource.__init__(self, text, amplitude, send)
