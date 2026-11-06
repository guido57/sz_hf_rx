#!/usr/bin/env python
"""Python 2.7/3 compatible bounded little-endian counter-stream checker."""
from __future__ import print_function
import os, struct, sys, time
count = int(sys.argv[1]) if len(sys.argv) > 1 else 1000000
if count <= 0:
    raise SystemExit('Word count must be positive')
fd = os.open('/dev/xillybus_read_32', os.O_RDONLY)
seen = 0
pending = b''
started = time.time()
try:
    while seen < count:
        chunk = os.read(fd, min(65536, (count-seen)*4-len(pending)))
        if not chunk:
            raise SystemExit('FAIL: unexpected end of stream')
        pending += chunk
        usable = len(pending)//4*4
        for value in struct.unpack('<%dI' % (usable//4), pending[:usable]):
            expected = seen & 0xffffffff
            if value != expected:
                raise SystemExit('FAIL at word %d: expected %d, received %d' % (seen, expected, value))
            seen += 1
        pending = pending[usable:]
finally:
    os.close(fd)
elapsed = time.time()-started
print('PASS: %d consecutive words, starting at zero (%.3f s)' % (seen, elapsed))
