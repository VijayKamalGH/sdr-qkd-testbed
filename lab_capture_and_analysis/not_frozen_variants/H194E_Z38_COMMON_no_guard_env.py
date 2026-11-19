"""Shared frame/qubit definitions for H1.94E V18-Z38 SDR-MIMO QKD (TX and analyzer must agree).

Spatial-qubit mapping (2 transmit antennas = 2-level system, amplitudes real):
    Z basis:  bit 0 -> (1, 0)            bit 1 -> (0, 1)
    X basis:  bit 0 -> (1, 1)/sqrt2      bit 1 -> (1,-1)/sqrt2
Vector component 1 is sent on TX1 (stream A), component 2 on TX2 (stream B), one BPSK-rate
symbol per qubit (200 samples). The 2x2 RF channel H plays the role of the channel; Receiver inverts
the measured H (public pilots) and then measures in a random basis, exactly like polarisation BB84.

Frame (480 symbols = 96000 samples = 48 ms):
    0..63    pilot A (TX1)          64..127  pilot B (TX2)
    128..143 frame index word (TX1 only): 8 bits idx + 8 bits ~idx
    144..415 272 qubit symbols      416..479 guard (zeros)
"""
import numpy as np

FS, FC, SPS, TONE_OFFSET = 2_000_000, 915_000_000, 200, 100_000
N_PILOT, N_IDX, N_Q, N_GUARD = 64, 16, 272, 64
N_SYM = 2 * N_PILOT + N_IDX + N_Q + N_GUARD        # 480
I0, Q0, Q1 = 2 * N_PILOT, 2 * N_PILOT + N_IDX, 2 * N_PILOT + N_IDX + N_Q
S2 = np.sqrt(0.5)
VEC = {(0, 0): (1.0, 0.0), (0, 1): (0.0, 1.0), (1, 0): (S2, S2), (1, 1): (S2, -S2)}  # (basis, bit)


def pilots():
    rs = np.random.RandomState(120396)
    pm = lambda b: 1.0 - 2.0 * b.astype(np.float64)
    return pm(rs.randint(0, 2, N_PILOT)), pm(rs.randint(0, 2, N_PILOT))


def sender_qubits(seed, idx):
    """Sender's basis and bit for every qubit of frame `idx` (deterministic from the seed)."""
    rs = np.random.RandomState([seed & 0x7FFFFFFF, idx])
    return rs.randint(0, 2, N_Q).astype(np.uint8), rs.randint(0, 2, N_Q).astype(np.uint8)


def idx_symbols(idx):
    b = np.unpackbits(np.array([idx & 255, (~idx) & 255], dtype=np.uint8))
    return 1.0 - 2.0 * b


def frame_streams(seed, idx, eve_rate=0.0, eve_rng=None):
    """Return (stream A symbols, stream B symbols) of one frame. Optional intercept-resend Eve."""
    pa, pb = pilots()
    basis, bit = sender_qubits(seed, idx)
    sa, sb = np.zeros(N_SYM), np.zeros(N_SYM)
    sa[:N_PILOT], sb[N_PILOT:2 * N_PILOT] = pa, pb
    sa[I0:Q0] = idx_symbols(idx)
    for k in range(N_Q):
        b, v = int(basis[k]), int(bit[k])
        if eve_rate > 0 and eve_rng.random() < eve_rate:      # Eve measures in a random basis, resends
            eb = int(eve_rng.integers(0, 2))
            if eb == b: ev = v
            else: ev = int(eve_rng.integers(0, 2))
            b, v = eb, ev
        a_, b_ = VEC[(b, v)]
        sa[Q0 + k], sb[Q0 + k] = a_, b_
    return sa, sb


def to_waveform(sym, amplitude):
    x = np.repeat(sym.astype(np.float32), SPS).astype(np.complex64)
    n = np.arange(len(x))
    return (amplitude * x * np.exp(2j * np.pi * TONE_OFFSET * n / FS)).astype(np.complex64)
