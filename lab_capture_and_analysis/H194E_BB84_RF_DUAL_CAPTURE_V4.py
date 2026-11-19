#!/usr/bin/env python3

import os
import argparse

from gnuradio import gr, blocks
import osmosdr

FS = 2_000_000
RF = 915_000_000
BW = 1_000_000

RX_GAINS = [20, 30]


class ReceiverDualCapture(gr.top_block):

    def __init__(self, seconds):

        super().__init__(
            "H194E BB84 RF DUAL CHANNEL CAPTURE"
        )

        self.source = osmosdr.source(
            args="numchan=2 bladerf=0,nchan=2"
        )

        self.source.set_sample_rate(FS)

        self.heads = []
        self.sinks = []

        for ch in range(2):

            self.source.set_center_freq(RF, ch)
            self.source.set_bandwidth(BW, ch)
            self.source.set_gain_mode(False, ch)
            self.source.set_gain(RX_GAINS[ch], ch)

            head = blocks.head(
                gr.sizeof_gr_complex,
                int(FS * seconds)
            )

            filename = (
                f"H194E_BB84_RF_RX{ch}_V4.c64"
            )

            sink = blocks.file_sink(
                gr.sizeof_gr_complex,
                filename,
                False
            )

            self.connect(
                (self.source, ch),
                head,
                sink
            )

            self.heads.append(head)
            self.sinks.append(sink)


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seconds",
        type=float,
        default=2.0
    )

    args = parser.parse_args()

    print("=" * 65)
    print("H1.94E — BB84 RF DUAL CHANNEL CAPTURE")
    print("=" * 65)

    print("SENDER (SENDER): bladeRF TX0")
    print("RECEIVER (RECEIVER): bladeRF RX0 + RX1")
    print("EAVESDROPPER (EVE): DISABLED")

    print(f"RF: {RF / 1e6:.3f} MHz")
    print(f"Sample rate: {FS / 1e6:.1f} MS/s")

    print(f"RX0 gain: {RX_GAINS[0]} dB")
    print(f"RX1 gain: {RX_GAINS[1]} dB")

    print(f"Capture duration: {args.seconds} s")

    tb = ReceiverDualCapture(args.seconds)

    print("\nStarting dual-channel capture...", flush=True)

    tb.run()

    print("\nCAPTURE COMPLETE")

    expected = int(FS * args.seconds) * 8

    success = True

    for ch in range(2):

        filename = f"H194E_BB84_RF_RX{ch}_V4.c64"

        if not os.path.exists(filename):
            print(f"{filename}: MISSING")
            success = False
            continue

        size = os.path.getsize(filename)

        print(f"{filename}: {size:,} bytes")

        if size != expected:
            success = False

    if success:
        print("\nDUAL CHANNEL IQ CAPTURE: PASS")
    else:
        print("\nDUAL CHANNEL IQ CAPTURE: FAIL")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
