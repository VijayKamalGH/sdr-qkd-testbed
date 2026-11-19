import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.QubitDecoder):
    """Receiver: sync, channel estimate, MMSE or ZF, random-basis measurement, sifting, QBER, Cascade, privacy amplification."""
    def __init__(self, seed=20261030, receiver_seed=777, batch_frames=40, key_frames=200, skip_first=0, reset=0, detector="MMSE"):
        qkd_grc.QubitDecoder.__init__(self, seed, receiver_seed, batch_frames, key_frames, skip_first, reset, detector)
