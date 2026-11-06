#!/usr/bin/env python3
"""Select the next ADC snapshot source; Python 3.5+ on Xillinux."""
import argparse,os

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('source',nargs='?',choices=['simulated','external'])
 p.add_argument('--device',default='/dev/xillybus_mem_8')
 a=p.parse_args()
 fd=os.open(a.device,os.O_RDWR)
 try:
  if a.source:
   os.lseek(fd,0,os.SEEK_SET)
   if os.write(fd,bytes([int(a.source=='external')]))!=1:raise RuntimeError('Short control write')
  os.lseek(fd,0,os.SEEK_SET)
  value=os.read(fd,1)
  if len(value)!=1:raise RuntimeError('Short control read')
  external=bool(value[0]&1)
  if a.source and external!=(a.source=='external'):raise RuntimeError('Source readback mismatch')
 finally:os.close(fd)
 print('Next capture: %s; adc_monitor.py --rate %d'%('external channel A' if external else 'simulated',8000000 if external else 64000000))
 print('Stop/restart the monitor when switching; an already open frame keeps its original source.')
if __name__=='__main__':main()
