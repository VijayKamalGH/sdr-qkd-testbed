import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.UdpRunner):
    """Public channel over UDP: BB84 sifting, test subset, verdict and reconciliation traffic between two computers."""
    def __init__(self, role="sender", peer="127.0.0.1:5005", listen=5006, n=40000, qch=0.02, q_eve=0.0, p_loss=0.0, go=0):
        qkd_grc.UdpRunner.__init__(self, role, peer, listen, n, qch, q_eve, p_loss, go)
