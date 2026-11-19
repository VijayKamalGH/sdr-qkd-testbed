#!/usr/bin/env python3
"""Phase 16b: BB84 with REAL Cascade reconciliation + Toeplitz privacy amplification, QBER taken from
Phase 20.3 receiver JSON files (--json res_*.json) or from the Phase 14b model (--gains 10 8 6 ...).
Errors are injected on the sifted key at the stream BER; leaked parity bits are counted exactly."""
import argparse, json, sys
import numpy as np
from scipy.stats import norm
h = lambda q: 0.0 if q <= 0 or q >= 1 else float(-q*np.log2(q)-(1-q)*np.log2(1-q))
Qf = lambda s: float(norm.sf(np.sqrt(2*10**(s/10))))
OFF = {'1': -4.58, '2': +1.00}

def cascade(ka, kb, q, rng, passes=4):
    """Receiver corrects kb to match ka. Returns (corrected kb, parity bits leaked)."""
    n = len(ka); kb = kb.copy(); leak = 0
    k1 = max(4, int(0.73/max(q, 1e-4))); perms = []; blocks = []
    def binary(idx):            # find one error in block idx (parity known to differ)
        nonlocal leak
        idx = np.asarray(idx)
        while len(idx) > 1:
            m = len(idx)//2; left = idx[:m]; leak += 1
            if (int(ka[left].sum())+int(kb[left].sum())) % 2: idx = left
            else: idx = idx[m:]
        kb[idx[0]] ^= 1; return int(idx[0])
    def fix(pi, bi):            # correct a block, then cascade back through earlier passes
        stack = [(pi, bi)]
        while stack:
            p, b = stack.pop()
            idx = blocks[p][b]
            if (int(ka[idx].sum())+int(kb[idx].sum())) % 2 == 0: continue
            pos = binary(idx)
            for pp in range(p):                # earlier passes containing this bit
                bb = where[pp][pos]; stack.append((pp, bb))
    where = []
    for p in range(passes):
        k = k1*(2**p)
        perm = np.arange(n) if p == 0 else rng.permutation(n)
        bl = [perm[i:i+k] for i in range(0, n, k)]
        blocks.append(bl); w = np.empty(n, dtype=int)
        for bi, b in enumerate(bl): w[b] = bi
        where.append(w); perms.append(perm)
        for bi, b in enumerate(bl):
            leak += 1                           # block parity disclosed
            if (int(ka[b].sum())+int(kb[b].sum())) % 2: fix(p, bi)
    return kb, leak

def toeplitz_pa(key, out_len, rng):
    n = len(key)
    if out_len <= 0: return np.zeros(0, dtype=np.uint8)
    t = rng.integers(0, 2, n+out_len-1, dtype=np.uint8)
    from scipy.signal import fftconvolve
    c = fftconvolve(t.astype(float), key.astype(float))[n-1:n-1+out_len]
    return (np.rint(c).astype(np.int64) % 2).astype(np.uint8)

def run(q, pulses, rng, test=0.1, eps=1e-6):
    ba = rng.integers(0, 2, pulses); bb = rng.integers(0, 2, pulses); bits = rng.integers(0, 2, pulses)
    s = ba == bb; ka = bits[s].astype(np.uint8); kb = ka ^ (rng.random(len(ka)) < q).astype(np.uint8)
    nt = int(test*len(ka)); idx = rng.permutation(len(ka)); t, k = idx[:nt], idx[nt:]
    qest = float(np.mean(ka[t] != kb[t])); qup = qest+np.sqrt(np.log(1/eps)/(2*nt))
    A, B = ka[k], kb[k]
    if qup > 0.11: return dict(abort=True, qest=qest, qup=qup)
    Bc, leak = cascade(A, B, max(qest, 1e-4), rng)
    ok = bool(np.array_equal(A, Bc)); n = len(A)
    L = int(max(0, np.floor(n*(1-h(qup))-leak-2*np.log2(1/eps))))
    pa = np.random.default_rng(int(rng.integers(1 << 30)))
    sa = toeplitz_pa(A, L, np.random.default_rng(5)); sb = toeplitz_pa(Bc, L, np.random.default_rng(5))
    return dict(abort=False, qest=qest, qup=qup, recon_ok=ok, leak=leak, f_eff=leak/(n*h(qest)) if qest > 0 else None,
                L=L, keys_equal=bool(np.array_equal(sa, sb)), skr=L/pulses, n=n)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', nargs='*', default=[]); ap.add_argument('--gains', nargs='*', type=float, default=[])
    ap.add_argument('--pulses', type=int, default=400000); ap.add_argument('--runs', type=int, default=5)
    ap.add_argument('--seed', type=int, default=3); a = ap.parse_args()
    rng = np.random.default_rng(a.seed); cases = []
    for fn in a.json:
        r = json.load(open(fn))
        for k in '12':
            if r.get('ber'+k) is not None: cases.append((f"{r.get('label') or fn} s{k}", r['ber'+k]))
    for g in a.gains:
        for k in '12': cases.append((f"G{g:g} s{k}", Qf(g+OFF[k])))
    print('case          BER_in   Q_est   Q_up   leak   f_eff  recon  keys=  key_bits  bits/pulse  abort')
    for name, q in cases:
        R = [run(q, a.pulses, rng) for _ in range(a.runs)]; ab = sum(r['abort'] for r in R); G = [r for r in R if not r['abort']]
        if not G: print(f'{name:12s} {q:8.4f}    -- all {a.runs} runs aborted (Q_up>11%)'); continue
        m = lambda k: np.mean([r[k] for r in G if r[k] is not None]) if any(r[k] is not None for r in G) else float('nan')
        print(f"{name:12s} {q:8.4f} {m('qest'):7.4f} {m('qup'):6.3f} {m('leak'):6.0f} {m('f_eff'):6.2f}  {all(r['recon_ok'] for r in G)!s:5s} {all(r['keys_equal'] for r in G)!s:5s} {m('L'):8.0f}  {m('skr'):9.4f}   {ab}/{a.runs}")
if __name__ == '__main__': main()
