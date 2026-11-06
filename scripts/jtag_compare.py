#!/usr/bin/env python
"""Xillinux 2.0 full-PL JTAG lifecycle. Use UART, not SSH. Python 2.7/3."""
from __future__ import print_function
import os,sys,json,glob,time,subprocess
STATE='/run/xillinux-jtag-state.json'
DRIVERS=['/sys/bus/spi/drivers/fb_st7789v',
 '/sys/bus/platform/drivers/xillyvga',
 '/sys/bus/platform/drivers/xillybus_lite_of',
 '/sys/bus/platform/drivers/xillybus_of']
def fail(s):raise SystemExit(s)
def run(args):return subprocess.check_output(args).decode('utf-8','replace')
def write(path,s):
 with open(path,'w') as f:f.write(s)
def save(s):
 with open(STATE+'.tmp','w') as f:json.dump(s,f,indent=2)
 os.rename(STATE+'.tmp',STATE)
def devices(driver):
 result=[]
 if not os.path.isdir(driver):return result
 for p in glob.glob(driver+'/*'):
  if os.path.islink(p) and os.path.realpath(p).startswith('/sys/devices/'):
   result.append(os.path.basename(p))
 return sorted(result)
def busy():
 hits=[]
 for p in glob.glob('/proc/[0-9]*'):
  if int(p.split('/')[-1])==os.getpid():continue
  try:
   with open(p+'/comm') as f:name=f.read().strip()
   for fd in glob.glob(p+'/fd/*'):
    try:target=os.readlink(fd)
    except OSError:continue
    if target.startswith(('/dev/xilly','/dev/fb','/dev/mem','/dev/spidev','/dev/i2c-')):
     hits.append('%s %s: %s'%(p.split('/')[-1],name,target))
   with open(p+'/maps') as f:
    for line in f:
     if any(v in line for v in ['/dev/xilly','/dev/fb','/dev/mem','/dev/spidev','/dev/i2c-']):
      hits.append('%s %s: mapped device'%(p.split('/')[-1],name));break
  except IOError:pass
 return sorted(set(hits))
def inventory():
 print(run(['uname','-r']).strip())
 for d in DRIVERS:print(d+': '+', '.join(devices(d)))
 for b in busy():print('BUSY '+b)
 for p in glob.glob('/sys/class/graphics/fb*/device/driver'):
  print(p+' -> '+os.path.realpath(p))
 print('Saved lifecycle state: '+str(os.path.exists(STATE)))
def prepare():
 if os.path.exists(STATE):fail('Existing lifecycle state: use status/finish or reboot; do not overwrite it.')
 users=busy()
 if users:fail('Close these applications first:\n'+'\n'.join(users))
 if not devices(DRIVERS[-1]) or not devices(DRIVERS[1]):
  fail('Expected bound xillybus_of and xillyvga drivers not found; refusing this board profile.')
 # Reject unknown framebuffer drivers, whose shutdown path was not reviewed.
 for p in glob.glob('/sys/class/graphics/fb*/device/driver'):
  if os.path.realpath(p) not in DRIVERS:fail('Unreviewed framebuffer driver: '+os.path.realpath(p))
 if not os.path.isdir('/sys/class/net/eth0'):fail('Expected eth0 not found.')
 flags=int(open('/sys/class/net/eth0/flags').read().strip(),16)
 s={'drivers':[],'consoles':[],'eth_was_up':bool(flags&1),'phase':'preparing'}
 s['networkmanager_active'] = subprocess.call(['systemctl','is-active','--quiet','NetworkManager']) == 0
 save(s)
 try:
  if s['networkmanager_active']:subprocess.check_call(['systemctl','stop','NetworkManager'])
  subprocess.check_call(['ip','link','set','dev','eth0','down'])
  for p in sorted(glob.glob('/sys/class/vtconsole/vtcon*')):
   if 'frame buffer' in open(p+'/name').read().lower() and open(p+'/bind').read().strip()=='1':
    s['consoles'].append(p);save(s);write(p+'/bind','0')
  before=run(['dmesg'])
  for d in DRIVERS:
   for dev in devices(d):
    if not os.path.exists(d+'/unbind'):fail('No unbind support: '+d)
    s['drivers'].append([d,dev]);save(s)
    write(d+'/unbind',dev)
    if os.path.exists('/sys/bus/platform/devices/'+dev+'/driver') and d.startswith('/sys/bus/platform'):
     fail('Device still bound: '+dev)
  after=run(['dmesg'])
  # Kernel removal returns void even when the FPGA quiesce handshake fails.
  # Fail closed on any new quiesce error (also handles log-ring rotation).
  prefix=after.startswith(before)
  new=after[len(before):] if prefix else after
  if 'Failed to quiesce' in new or 'Hardware left in messy state' in new:
   s['phase']='unsafe-reboot-required';save(s)
   fail('DMA shutdown failed. DO NOT program JTAG. Reboot the working SD image.')
  if glob.glob('/dev/xillybus*'):fail('Xillybus device nodes remain; do not program JTAG.')
  time.sleep(.1)
  s['phase']='prepared';save(s)
  print('PREPARED: drivers detached and eth0 down. Program the compatible full bitstream via JTAG now.')
  print('After Vivado reports successful programming, run: python /root/sz_hf_rx/scripts/jtag_lifecycle.py finish')
 except (IOError,OSError,subprocess.CalledProcessError) as e:
  fail('Prepare failed: %s. DO NOT program. State saved; restore with finish or reboot.'%e)
def finish():
 if not os.path.exists(STATE):fail('No prepared lifecycle state exists.')
 with open(STATE) as f:s=json.load(f)
 if s['phase']=='unsafe-reboot-required':fail('Shutdown was unsafe; reboot rather than rebind.')
 s['phase']='restoring';save(s)
 before=run(['dmesg'])
 try:
  # Discovery of Xillybus comes first, then Lite, then framebuffers.
  for d,dev in reversed(s['drivers']):
   if dev not in devices(d):write(d+'/bind',dev)
   if dev not in devices(d):fail('Rebind failed: '+dev+'; inspect dmesg and reboot if necessary.')
   after=run(['dmesg'])
   new=after[len(before):] if after.startswith(before) else after
   failures=[ 'Lost sync with interrupt messages', 'Failed to quiesce', 'Failed to obtain IDT', 'IDT failed CRC', 'Hardware left in messy state']
   # One warning before discovery completed was observed with a passing
   # hardware capture. Treat it as unverified, not a fatal verdict.
   bad_lines=[i for i,line in enumerate(new.splitlines()) if 'Bad interrupt message' in line]
   created_lines=[i for i,line in enumerate(new.splitlines()) if 'xillybus' in line and 'Created ' in line and 'device files' in line]
   if bad_lines:
    if created_lines and max(bad_lines)<max(created_lines):
     print('WARNING: interrupt message during discovery; a bounded transfer test is required.')
    else:
     s['phase']='unsafe-reboot-required';save(s)
     fail('Interrupt error without completed discovery. Reboot the working SD image.')
   if any(msg in new for msg in failures):
    s['phase']='unsafe-reboot-required';save(s)
    fail('Driver error during rebind; recovery is NOT verified. State retained. Reboot the working SD image and collect dmesg.')
  for p in s['consoles']:
   if os.path.exists(p+'/bind'):write(p+'/bind','1')
  if s['eth_was_up']:subprocess.check_call(['ip','link','set','dev','eth0','up'])
  if s.get('networkmanager_active'):subprocess.check_call(['systemctl','start','NetworkManager'])
  nodes=glob.glob('/dev/xillybus_read_32')
  if not nodes:fail('Xillybus read_32 endpoint missing after rebind.')
  s['phase']='restored';save(s)
  os.unlink(STATE)
  print('REBOUND: no immediate driver errors detected; capture and network tests still required.')
  print('Check ip -4 addr show eth0 and run the bounded capture test. DHCP/SSH may take time.')
 except (IOError,OSError,subprocess.CalledProcessError) as e:
  fail('Restore failed: %s. Inspect dmesg; state retained for retry or recovery reboot.'%e)
if __name__=='__main__':
 action=sys.argv[1] if len(sys.argv)==2 else 'status'
 if action not in ['status','prepare','finish']:fail('Usage: jtag_lifecycle.py status|prepare|finish')
 if action=='status':inventory()
 else:
  if os.geteuid()!=0:fail('Run as root.')
  if os.environ.get('SSH_CONNECTION') or os.environ.get('SSH_TTY'):
   fail('Run prepare/finish from the UART console, not SSH: Ethernet will be interrupted.')
  if not sys.stdin.isatty():fail('Use an interactive UART console.')
  if action=='prepare':prepare()
  else:finish()
