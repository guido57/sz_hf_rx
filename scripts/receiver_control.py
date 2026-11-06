#!/usr/bin/env python3
"""Atomic DDC receiver controls, compatible with Python 3.5 (no NumPy needed)."""
import os
import signal
import math
from contextlib import contextmanager

RATE = 64000000
MARKER = 0xd2
SSB_MARKER = 0xd3
MODE_CODES = {'raw': 0, 'iq': 1, 'usb': 2, 'lsb': 3}
MODE_LABELS = ['Raw ADC', 'DDC I/Q', 'USB audio', 'LSB audio']

@contextmanager
def deadline(seconds):
    def expired(signum, frame):
        raise RuntimeError('Receiver control/capture timed out')
    old = signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

def phase_for_hz(hz):
    hz = float(hz)
    if not math.isfinite(hz) or not 0 <= hz < RATE / 2:
        raise ValueError('Frequency must be at least 0 and below 32000000 Hz')
    return int(round(hz * (1 << 48) / RATE))

def phase_bytes(phase):
    return bytes(bytearray((phase >> (8 * n)) & 255 for n in range(6)))

def phase_value(data):
    return sum(value << (8 * n) for n, value in enumerate(bytearray(data)))

def _read_bytes(device, timeout=10):
    with deadline(timeout):
        fd = os.open(device, os.O_RDWR)
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            data = os.read(fd, 16)
        finally:
            os.close(fd)
    if len(data) != 16 or data[3] not in (MARKER, SSB_MARKER):
        raise RuntimeError('This bitstream does not provide DDC receiver controls')
    return data

def read_config(device, timeout=10):
    data = _read_bytes(device, timeout)
    mode = (data[1] & 3) if data[3] == SSB_MARKER else (data[1] & 1)
    return {'source': 'external' if data[0] & 1 else 'simulated',
            'mode': ['raw', 'iq', 'usb', 'lsb'][mode],
            'tune_phase': phase_value(data[4:10]),
            'sim_phase': phase_value(data[10:16])}

def configure(device, settings, timeout=10):
    if settings['mode'] not in MODE_CODES:
        raise ValueError('Unknown receiver mode')
    if settings['mode'] in ('usb', 'lsb') and _read_bytes(device, timeout)[3] != SSB_MARKER:
        raise RuntimeError('USB/LSB requires the SSB bitstream (marker 0xd3)')
    flags = bytes(bytearray([int(settings['source'] == 'external'),
                             MODE_CODES[settings['mode']]]))
    phases = phase_bytes(settings['tune_phase']) + phase_bytes(settings['sim_phase'])
    with deadline(timeout):
        fd = os.open(device, os.O_RDWR)
        try:
            for offset, data in [(0, flags), (4, phases), (2, b'\x01')]:
                os.lseek(fd, offset, os.SEEK_SET)
                if os.write(fd, data) != len(data):
                    raise RuntimeError('Short receiver configuration write')
        finally:
            os.close(fd)
    actual = read_config(device, timeout)
    if actual != settings:
        raise RuntimeError('Receiver configuration readback mismatch')
    return actual

class ReceiverController(object):
    def __init__(self, device, timeout, source=None, mode=None, tune=None, sim=None):
        self.device, self.timeout = device, timeout
        self.settings = read_config(device, timeout)
        self.pending = {}
        if source is not None:
            self.pending['source'] = source
        if mode is not None:
            self.pending['mode'] = mode
        if tune is not None:
            self.pending['tune_phase'] = phase_for_hz(tune)
        if sim is not None:
            self.pending['sim_phase'] = phase_for_hz(sim)
        self.apply_pending()

    @property
    def source(self):
        return self.settings['source']

    @property
    def mode(self):
        return self.settings['mode']

    @property
    def rate(self):
        return 8000. if self.mode != 'raw' else float(RATE)

    def frequency(self, name):
        return self.settings[name + '_phase'] * RATE / float(1 << 48)

    def request(self, label):
        self.pending['source'] = 'external' if label == 'External ADC' else 'simulated'

    def request_mode(self, label):
        self.pending['mode'] = ['raw', 'iq', 'usb', 'lsb'][MODE_LABELS.index(label)]

    def request_frequency(self, name, hz):
        self.pending[name + '_phase'] = phase_for_hz(hz)

    def apply_pending(self):
        if self.pending:
            updated = dict(self.settings)
            updated.update(self.pending)
            self.settings = configure(self.device, updated, self.timeout)
            self.pending.clear()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', default='/dev/xillybus_mem_8')
    parser.add_argument('--timeout', type=int, default=10)
    parser.add_argument('--source', choices=['external', 'simulated'])
    parser.add_argument('--mode', choices=['raw', 'iq', 'usb', 'lsb'])
    parser.add_argument('--tune', type=float)
    parser.add_argument('--sim-frequency', type=float)
    args = parser.parse_args()
    try:
        controller = ReceiverController(args.device, args.timeout, args.source,
                                        args.mode, args.tune, args.sim_frequency)
        print('%s | %s | tune %.3f Hz | simulator %.3f Hz | %.0f samples/s' %
              (controller.source, controller.mode, controller.frequency('tune'),
               controller.frequency('sim'), controller.rate))
    except (RuntimeError, ValueError, OSError) as error:
        parser.exit(1, 'ERROR: %s\n' % error)
