import sys
p = "H194E_BPSK_TX_V18Z34.py"
s = open(p).read()
if "--nchan" in s:
    sys.exit("already patched")
def sub(old, new, count):
    global s
    n = s.count(old)
    if n != count:
        sys.exit(f"ANCHOR MISMATCH ({n} found, expected {count}): {old[:50]!r}")
    s = s.replace(old, new)
sub("    args = parser.parse_args()\n",
'''    parser.add_argument(
        "--nchan", type=int, choices=[1, 2], default=2,
        help="1 = single-channel (SISO) transmit on TX0 only; 2 = dual-channel (default)",
    )
    args = parser.parse_args()
    if args.nchan == 1 and args.mode != "tx0":
        parser.error("--nchan 1 transmits on TX0 only: use --mode tx0")
''', 1)
sub('sink = osmosdr.sink(args="numchan=2 bladerf=0,nchan=2")',
    'sink = osmosdr.sink(args=f"numchan={args.nchan} bladerf=0,nchan={args.nchan}")', 1)
sub("for ch in range(2):", "for ch in range(args.nchan):", 2)
sub('    if args.mode == "both":\n        rot =',
    '    if args.nchan == 1:\n        tb.connect(source, (sink, 0))\n    elif args.mode == "both":\n        rot =', 1)
sub('print(f"Mode: {args.mode}")', 'print(f"Mode: {args.mode}   channels: {args.nchan}")', 1)
open(p, "w").write(s)
print("patched OK")
