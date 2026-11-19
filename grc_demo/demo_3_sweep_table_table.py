import os, sys
for _p in (os.getcwd(), os.environ.get("QKD_GRC_DIR", ""), os.path.expanduser("~/grc_demo")):
    if _p and _p not in sys.path: sys.path.insert(0, _p)
import qkd_grc

class blk(qkd_grc.ResultsTable):
    """Stored fresh-sweep results (W1/W2): pick a capture, read its numbers."""
    def __init__(self, idx=0, table="w1w2_table.json"):
        qkd_grc.ResultsTable.__init__(self, idx, table)
