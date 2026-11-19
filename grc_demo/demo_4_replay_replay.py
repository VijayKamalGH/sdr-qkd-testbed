import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.CaptureReplay):
    """Plays two stored capture files (RX0, RX1) in a loop; a missing file only prints a message."""
    def __init__(self, rx0_file="H194E_V18Z34_SWW203_ON_RX0.c64", rx1_file="H194E_V18Z34_SWW203_ON_RX1.c64"):
        qkd_grc.CaptureReplay.__init__(self, rx0_file, rx1_file)
