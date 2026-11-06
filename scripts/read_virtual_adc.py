#!/usr/bin/env python
from __future__ import print_function
import os,struct,math,sys
fd=os.open('/dev/xillybus_read_32',os.O_RDONLY);raw=b''
try:
 while True:
  b=os.read(fd,16384)
  if not b:break
  raw+=b
  if len(raw)>16384:raise SystemExit('FAIL: more than 4096 words')
finally:os.close(fd)
if len(raw)!=16384:raise SystemExit('FAIL: expected 16384 bytes, received %d'%len(raw))
words=struct.unpack('<4096I',raw);samples=[]
for i,w in enumerate(words):
 if w>>16!=i:raise SystemExit('FAIL: index mismatch at %d'%i)
 v=w&65535;samples.append(v-65536 if v&32768 else v)
 if samples[-1]<-8192 or samples[-1]>8191:raise SystemExit('FAIL: invalid 14-bit signed code')
name=sys.argv[1] if len(sys.argv)>1 else '/root/virtual_adc'
with open(name+'.bin','wb') as f:f.write(raw)
with open(name+'.csv','w') as f:
 f.write('index,time_seconds,sample\n')
 for i,v in enumerate(samples):f.write('%d,%.12f,%d\n'%(i,i/64000000.0,v))
if max(samples)==min(samples):raise SystemExit('FAIL: constant input')
if any(samples[i]!=samples[i+64] for i in range(len(samples)-64)):
 raise SystemExit('FAIL: waveform is not the expected 64-sample repeating tone')
print('PASS: 4096 indexed signed samples; exact 64-sample repetition (1 MHz at 64 MS/s)')
print('min=%d max=%d mean=%.2f'%(min(samples),max(samples),sum(samples)/4096.0))
print('Saved '+name+'.bin and '+name+'.csv')
