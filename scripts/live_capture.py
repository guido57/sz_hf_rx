#!/usr/bin/env python3
"""Run the SmartZynq internal FT8 demo or external receiver (Python 3.5+)."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=('simulated', 'external'), default='simulated')
    parser.add_argument('--tune', type=float, default=14074000.0, help='RF tuning in Hz')
    parser.add_argument('--offset', type=float, default=1500.0, help='simulated audio offset in Hz')
    parser.add_argument('--slots', type=int, default=1, help='number of 15-second slots')
    args = parser.parse_args(argv)
    from receiver_control import phase_for_hz
    try:
        phase_for_hz(args.tune)
        if args.source == 'simulated':
            phase_for_hz(args.tune + args.offset)
            if not 150 <= args.offset <= 3000:
                raise ValueError('Simulated audio offset must be between 150 and 3000 Hz')
        if not 1 <= args.slots <= 1000000:
            raise ValueError('Slot count must be between 1 and 1000000')
    except ValueError as error:
        parser.error(str(error))
    root = Path(__file__).resolve().parents[1]
    binary = root / 'ft8_decoder/build/a9-stream/ft8-subtract-stream-a9'
    if not binary.is_file() or not os.access(str(binary), os.X_OK):
        parser.exit(1, 'Decoder missing; run python3 scripts/install_sd.py first.\n')
    for name in ('/dev/xillybus_mem_8', '/dev/xillybus_read_8'):
        if not os.path.exists(name):
            parser.exit(1, 'Missing %s; boot the compatible hf_ssb_receiver PL image.\n' % name)
    if os.geteuid() != 0:
        parser.exit(1, 'Run this command as root on Xillinux.\n')
    from receiver_control import ReceiverController, _read_bytes
    from ft8_control import upload, K1ABC
    try:
        if _read_bytes('/dev/xillybus_mem_8', 3)[3] != 0xd3:
            raise RuntimeError('The loaded FPGA image does not provide SSB audio')
        print('Selecting %s source, USB audio, tuning %.0f Hz.' %
              (args.source, args.tune), flush=True)
        ReceiverController('/dev/xillybus_mem_8', 3, args.source, 'usb', args.tune,
                           args.tune + args.offset if args.source == 'simulated' else None)
        if args.source == 'simulated':
            print('Uploading the internal test message: G0XYZ K1ABC FN43.', flush=True)
            upload(K1ABC)
        print('Capturing %d slot(s). First output can take 30 seconds. Ctrl+C stops capture.' %
              args.slots, flush=True)
        command = [str(binary), '--slots', str(args.slots),
                   '--base-mhz', '%.9f' % (args.tune / 1e6)]
        # Bound stalled hardware reads; leave time for capture and decoding.
        subprocess.run(command, check=True, timeout=30 + 20 * args.slots)
    except subprocess.TimeoutExpired:
        parser.exit(1, 'Capture timed out. Check the PL image, USB mode and competing readers.\n')
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Capture failed: %s\n' % error)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
