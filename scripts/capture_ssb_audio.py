#!/usr/bin/env python3
"""Record continuous PL-demodulated PCM16 as an 8 kHz mono WAV (Python 3.5)."""
import argparse,sys,os,wave,time
from receiver_control import ReceiverController,deadline,_read_bytes

def read_audio_status(device):
 fd=os.open(device,os.O_RDONLY)
 try:
  os.lseek(fd,16,os.SEEK_SET);return os.read(fd,1)
 finally:os.close(fd)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('output');p.add_argument('--mode',choices=['usb','lsb'],default='usb')
 p.add_argument('--source',choices=['external','simulated'])
 p.add_argument('--tune',type=float);p.add_argument('--sim-frequency',type=float)
 p.add_argument('--device',default='/dev/xillybus_read_8')
 p.add_argument('--control-device',default='/dev/xillybus_mem_8');p.add_argument('--seconds',type=float,default=5)
 p.add_argument('--timeout',type=int,default=10)
 p.add_argument('--settle',type=float,default=.05,help='seconds to settle after tuning, before opening audio')
 a=p.parse_args()
 if not 0<=a.settle<=5:p.error('--settle must be between 0 and 5 seconds')
 if a.timeout<1:p.error('--timeout must be positive')
 if not 0<a.seconds<=3600:p.error('--seconds must be between 0 and 3600')
 c=ReceiverController(a.control_device,a.timeout,a.source,a.mode,a.tune,a.sim_frequency)
 frames=int(round(a.seconds*8000));remaining=frames*2
 if frames<1:p.error('Recording duration is less than one audio sample')
 time.sleep(a.settle)
 with deadline(int(a.seconds)+a.timeout):
  fd=os.open(a.device,os.O_RDONLY)
  try:
   with wave.open(a.output,'wb') as wav:
    wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000)
    while remaining:
     data=os.read(fd,min(remaining,16384))
     if not data:raise RuntimeError('Continuous audio stream ended early')
     wav.writeframesraw(data);remaining-=len(data)
   # Check while still open: closing the stream clears its overflow latch.
   if _read_bytes(a.control_device,a.timeout)[3]!=0xd3:raise RuntimeError('SSB bitstream required')
   with deadline(a.timeout):
    status=read_audio_status(a.control_device)
   if len(status)!=1 or status[0]&1:raise RuntimeError('Audio FIFO overflow: recording has lost samples')
  finally:os.close(fd)
 print('Saved %s: %d continuous mono samples, 8000 Hz, %s' % (a.output,frames,c.mode.upper()))
if __name__=='__main__':
 try:main()
 except (RuntimeError,ValueError,OSError) as e:sys.exit('ERROR: '+str(e))
