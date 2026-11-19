#!/usr/bin/env python3
"""Phase A: classical-link model for the public channel, built from SDR measurements.
Parameters come from the SDR captures (frame time, frame-loss rate, goodput).
Used by the BB84 driver; no SDR hardware or NetSquid needed."""
import json, numpy as np

class ClassicalLink:
    """Sender<->Receiver public channel: one message = ceil(bits/payload) frames.
    Each frame takes t_frame s; lost with prob p_loss and then resent (stop-and-wait)."""
    def __init__(self, t_frame=0.048, payload_bits=272, p_loss=0.0, rtt_extra=0.0, seed=1):
        self.t, self.pl, self.p, self.rtt, self.rng = t_frame, payload_bits, p_loss, rtt_extra, np.random.default_rng(seed)
        self.time, self.bits, self.frames = 0.0, 0, 0
    @classmethod
    def from_capture_json(cls, path, **kw):
        d = json.load(open(path))
        return cls(p_loss=float(d.get("frame_loss", 0.0)), **kw)
    def send(self, nbits):
        n = int(np.ceil(nbits / self.pl)); tot = 0
        for _ in range(n):
            k = 1
            while self.rng.random() < self.p: k += 1
            tot += k
        self.frames += tot; self.bits += nbits
        dt = tot * (self.t + self.rtt); self.time += dt
        return dt
