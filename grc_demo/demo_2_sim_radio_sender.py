import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.QubitSource):
    """Sender: builds the frozen frame (pilots, index word, 272 spatial qubits) on TX1/TX2. eve_rate = share of qubits an eavesdropper intercepts."""
    def __init__(self, seed=20261030, amplitude=0.14, eve_rate=0.0):
        qkd_grc.QubitSource.__init__(self, seed, amplitude, eve_rate)
