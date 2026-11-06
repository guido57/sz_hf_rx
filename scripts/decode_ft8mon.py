#!/usr/bin/env python3
"""Decode a WAV with independent FT8MON processes on the two PS cores."""
import argparse
import os
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wav')
    parser.add_argument('--decoder', default='/root/ft8mon/ft8mon-cached')
    parser.add_argument('--budget', type=float, default=12)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    if not 0 < args.budget <= 3600:
        parser.error('--budget must be between 0 and 3600 seconds')
    # Overlap exceeds the 43.75 Hz FT8 tone span. Separate processes keep
    # the fork's mutable FFT caches isolated.
    ranges = [(150, 3600)] if args.workers == 1 else [(150, 1925), (1825, 3600)]
    started = time.monotonic()
    processes = []
    with tempfile.TemporaryDirectory(prefix='ft8mon-') as directory:
        try:
            for index, (low, high) in enumerate(ranges):
                env = dict(os.environ, FT8MON_BUDGET=str(args.budget),
                           FT8MON_MIN_HZ=str(low), FT8MON_MAX_HZ=str(high))
                output = open(os.path.join(directory, str(index)), 'w+')
                processes.append((None, output))
                process = subprocess.Popen([args.decoder, '-file', args.wav],
                                           env=env, stdout=output)
                processes[-1] = (process, output)
            failed = False
            for process, output in processes:
                failed = process.wait() != 0 or failed
            if failed:
                raise RuntimeError('FT8MON worker failed')
            seen = set()
            for process, output in processes:
                output.seek(0)
                for line in output:
                    if ' ~ ' not in line:
                        continue
                    key = ' '.join(line.split(' ~ ', 1)[1].split())
                    if key not in seen:
                        seen.add(key)
                        sys.stdout.write(line)
            print('%d unique message strings; %.3f seconds elapsed' %
                  (len(seen), time.monotonic() - started), file=sys.stderr)
        finally:
            for process, output in processes:
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait()
                output.close()


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as error:
        sys.exit(str(error))
