#!/usr/bin/env python3
"""Upload 79 FT8 tones through the PS Xillybus control window (Python 3.5+)."""
import argparse
import os
import time
from receiver_control import deadline

K1ABC = [3,1,4,0,6,5,2,0,3,1,7,4,5,2,6,4,5,0,5,4,7,6,7,0,4,6,0,6,0,2,1,4,3,2,0,5,3,1,4,0,6,5,2,6,4,0,4,0,1,3,6,5,0,5,4,5,4,5,0,7,0,6,4,0,4,1,1,4,0,0,4,2,3,1,4,0,6,5,2]

def pack_tones(tones):
    if len(tones) != 79 or any(type(t) is not int or not 0 <= t <= 7 for t in tones):
        raise ValueError('Expected exactly 79 integer tones in 0..7')
    value = sum(t << (3*n) for n,t in enumerate(tones))
    return bytes(bytearray((value >> (8*n)) & 255 for n in range(30)))

def upload(tones, device='/dev/xillybus_mem_8', timeout=10):
    payload = pack_tones(tones)
    with deadline(timeout):
        fd = os.open(device, os.O_RDWR)
        try:
            def read(offset):
                os.lseek(fd,offset,os.SEEK_SET)
                value=os.read(fd,1)
                if len(value)!=1: raise RuntimeError('Short control read')
                return value[0]
            def write(offset,value):
                os.lseek(fd,offset,os.SEEK_SET)
                if os.write(fd,bytes(bytearray([value])))!=1: raise RuntimeError('Short control write')
            if read(20)!=0xf8: raise RuntimeError('PS FT8 upload requires the new bitstream')
            while read(19) not in (0,3): time.sleep(.01)
            for index,value in enumerate(payload):
                write(17,index);write(18,value)
                if read(18)!=value: raise RuntimeError('FT8 byte readback mismatch')
            previous=read(19)&1
            write(19,1)
            expected=3 if previous==0 else 0
            while read(19)!=expected: time.sleep(.01)
        finally:
            os.close(fd)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tones',help='79 comma/space separated tone numbers; defaults to supplied K1ABC sequence')
    p.add_argument('--device',default='/dev/xillybus_mem_8')
    a=p.parse_args()
    try:
        tones=K1ABC if a.tones is None else [int(x) for x in a.tones.replace(',',' ').split()]
        upload(tones,a.device)
        print('Uploaded and acknowledged 79 FT8 tones; simulator restarted at symbol 0.')
    except (OSError,ValueError,RuntimeError) as e:
        p.exit(1,'ERROR: %s\n'%e)
