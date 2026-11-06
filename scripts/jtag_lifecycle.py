#!/usr/bin/env python3
"""Xillinux 2.0 full-PL JTAG lifecycle. Use UART, not SSH. Python 3.5+. Candidate HDMI drain/rearm fix."""
from __future__ import print_function
import os,sys,json,glob,time,subprocess,fcntl,mmap,struct
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
# Hardware profile: existing SmartZynq/Xillinux xillyvga at 0x50001000,
# AXI HP2 at 0xf800a000. The PS 100 MHz fabric clock MUST stay running.
VGA_BASE=0x50001000
HP2_BASE=0xf800a000
DRAIN_SECONDS=2.0
QUIET_SECONDS=0.10

def framebuffer_info():
 for path in sorted(glob.glob('/sys/class/graphics/fb*')):
  if os.path.realpath(path+'/device/driver')!=DRIVERS[1]:continue
  fd=os.open('/dev/'+os.path.basename(path),os.O_RDONLY)
  try:
   fix=fcntl.ioctl(fd,0x4602,bytes(80))
   var=fcntl.ioctl(fd,0x4600,bytes(160))
  finally:os.close(fd)
  info={'device':os.path.basename(path),'physical':struct.unpack_from('<I',fix,16)[0],
        'length':struct.unpack_from('<I',fix,20)[0],
        'stride':struct.unpack_from('<I',fix,44)[0],
        'width':struct.unpack_from('<I',var,8)[0],
        'height':struct.unpack_from('<I',var,12)[0],
        'bpp':struct.unpack_from('<I',var,24)[0]}
  if info['bpp']!=32 or info['stride']!=info['width']*4 or info['width']*info['height']%16:
   fail('Unsupported framebuffer layout; no register writes performed.')
  if info['length']<info['stride']*info['height'] or info['physical']%64:
   fail('Invalid framebuffer allocation; no register writes performed.')
  return info
 fail('Bound Xillyvga framebuffer not found.')

class RegisterPage(object):
 def __init__(self,address):
  self.fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC)
  try:self.mem=mmap.mmap(self.fd,4096,mmap.MAP_SHARED,mmap.PROT_READ|mmap.PROT_WRITE,offset=address)
  except BaseException:os.close(self.fd);raise
 def read(self,offset):return struct.unpack_from('<I',self.mem,offset)[0]
 def write(self,offset,value):self.mem[offset:offset+4]=struct.pack('<I',value)
 def close(self):self.mem.close();os.close(self.fd)

def hardware_profile():
 if not os.uname()[4].startswith('armv7'):
  fail('This register profile requires 32-bit ARM Zynq-7000.')
 bound=devices(DRIVERS[1])
 if bound!=['50001000.xillyvga']:fail('Unsupported HDMI device address: '+str(bound))
 node='/sys/bus/platform/devices/'+bound[0]+'/of_node'
 parent=os.path.dirname(os.path.realpath(node))
 def cells(name,default):
  path=parent+'/'+name
  if not os.path.exists(path):return default
  with open(path,'rb') as f:data=f.read()
  if len(data)!=4:fail('Invalid device-tree cell count: '+path)
  return struct.unpack('>I',data)[0]
 address_cells=cells('#address-cells',2)
 size_cells=cells('#size-cells',1)
 if address_cells not in (1,2) or size_cells not in (1,2):
  fail('Unsupported device-tree address layout; no register writes performed.')
 with open(node+'/reg','rb') as f:reg=f.read()
 entry_bytes=4*(address_cells+size_cells)
 if len(reg)<entry_bytes or len(reg)%entry_bytes:
  fail('Invalid HDMI device-tree reg property.')
 values=struct.unpack('>'+'I'*(len(reg)//4),reg)
 base=0
 for value in values[:address_cells]:base=(base<<32)|value
 if base!=VGA_BASE:fail('HDMI resource address does not match the reviewed driver.')


def sample_hp2(port):
 # Debug counter is logged only, never used as a functional completion flag.
 return {'read_control':port.read(0x00),'fifo_qwords':port.read(0x0c)&255,
         'read_debug':port.read(0x10),'write_control':port.read(0x14)}

def wait_empty(port,timeout=DRAIN_SECONDS):
 deadline=time.monotonic()+timeout;quiet=None;last=None
 while time.monotonic()<deadline:
  level=port.read(0x0c)&255;last=level
  now=time.monotonic()
  if level==0:
   if quiet is None:quiet=now
   if now-quiet>=QUIET_SECONDS:return
  else:quiet=None
  time.sleep(.01)
 raise RuntimeError('HP2 read FIFO did not drain (last level %s). DO NOT program JTAG; reboot.'%last)

def stop_hdmi(s):
 hardware_profile()
 s['hdmi_before']=framebuffer_info();save(s)
 hp=RegisterPage(HP2_BASE);vga=None
 try:
  s['hp2_before']=sample_hp2(hp);save(s)
  vga=RegisterPage(VGA_BASE)
  # Same display-control write as xillyvga_release(), but BEFORE freeing RAM.
  vga.write(0x08,0)
  s['hdmi_stopped']=True;save(s)
  wait_empty(hp)
  s['hp2_drained']=sample_hp2(hp);save(s)
  print('HDMI stopped; HP2 data FIFO observed empty for 100 ms before framebuffer release.')
 finally:
  if vga is not None:vga.close()
  hp.close()

def rearm_hdmi(s):
 hardware_profile();info=framebuffer_info()
 # Use the NEW driver's allocation, never the pre-JTAG physical address.
 hp=RegisterPage(HP2_BASE);vga=None
 try:
  vga=RegisterPage(VGA_BASE)
  vga.write(0x08,0)
  wait_empty(hp)
  # Match xillyvga_assign(): preserve unrelated HP2 fields, select 32-bit data.
  hp.write(0x00,hp.read(0x00)|1)
  hp.write(0x14,hp.read(0x14)|1)
  vga.write(0x10,info['physical'])
  vga.write(0x0c,info['width']*info['height']//16)
  vga.write(0x08,1)
  time.sleep(.05)
  s['hdmi_after']=info;s['hp2_after']=sample_hp2(hp);save(s)
  print('HDMI DMA rearmed with framebuffer at 0x%08x.'%info['physical'])
 finally:
  if vga is not None:vga.close()
  hp.close()

def save_diagnostics(s):
 directory='/root/jtag-diagnostics'
 if not os.path.isdir(directory):os.makedirs(directory)
 name=time.strftime('%Y%m%d-%H%M%S')+'-'+str(os.getpid())
 with open(directory+'/'+name+'.json','w') as f:json.dump(s,f,indent=2)
 with open(directory+'/'+name+'-dmesg.txt','w') as f:f.write(run(['dmesg']))
 print('Diagnostics: '+directory+'/'+name+'.json')


def prepare():
 if os.path.exists(STATE):fail('Existing lifecycle state: use status/finish or reboot; do not overwrite it.')
 sessions=run(['pgrep','-af','Xorg|xinit|lxsession']) if subprocess.call(['pgrep','-f','Xorg|xinit|lxsession'],stdout=subprocess.DEVNULL)==0 else ''
 if sessions.strip():fail('Log out of X/LXDE before prepare:\n'+sessions)
 users=busy()
 if users:fail('Close these applications first:\n'+'\n'.join(users))
 if not devices(DRIVERS[-1]) or not devices(DRIVERS[1]):
  fail('Expected bound xillybus_of and xillyvga drivers not found; refusing this board profile.')
 # Reject unknown framebuffer drivers, whose shutdown path was not reviewed.
 for p in glob.glob('/sys/class/graphics/fb*/device/driver'):
  if os.path.realpath(p) not in DRIVERS:fail('Unreviewed framebuffer driver: '+os.path.realpath(p))
 if not os.path.isdir('/sys/class/net/eth0'):fail('Expected eth0 not found.')
 hardware_profile() # Validate before changing network or console state.
 framebuffer_info()
 flags=int(open('/sys/class/net/eth0/flags').read().strip(),16)
 s={'version':2,'drivers':[],'consoles':[],'eth_was_up':bool(flags&1),'phase':'preparing'}
 s['networkmanager_active'] = subprocess.call(['systemctl','is-active','--quiet','NetworkManager']) == 0
 save(s)
 try:
  if s['networkmanager_active']:subprocess.check_call(['systemctl','stop','NetworkManager'])
  subprocess.check_call(['ip','link','set','dev','eth0','down'])
  for p in sorted(glob.glob('/sys/class/vtconsole/vtcon*')):
   if 'frame buffer' in open(p+'/name').read().lower() and open(p+'/bind').read().strip()=='1':
    s['consoles'].append(p);save(s);write(p+'/bind','0')
  before=run(['dmesg'])
  stop_hdmi(s)
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
  hp=RegisterPage(HP2_BASE)
  try:wait_empty(hp)
  finally:hp.close()
  time.sleep(.1)
  s['phase']='prepared';save(s)
  save_diagnostics(s)
  print('PREPARED: drivers detached and eth0 down. Program the compatible full bitstream via JTAG now.')
  print('After Vivado reports successful programming, run: python3 /root/sz_hf_rx/scripts/jtag_lifecycle.py finish')
 except (IOError,OSError,RuntimeError,subprocess.CalledProcessError) as e:
  save_diagnostics(s)
  fail('Prepare failed: %s. DO NOT program. State retained; reboot the working SD image.'%e)
def finish():
 if not os.path.exists(STATE):fail('No prepared lifecycle state exists.')
 with open(STATE) as f:s=json.load(f)
 if s['phase']=='unsafe-reboot-required':fail('Shutdown was unsafe; reboot rather than rebind.')
 if s.get('version')!=2:fail('State from an older script: reboot and prepare again with this version.')
 s['phase']='restoring';save(s)
 before=run(['dmesg']);warned=False
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
     if not warned:print('WARNING: interrupt message during discovery; a bounded transfer test is required.')
     warned=True
    else:
     s['phase']='unsafe-reboot-required';save(s)
     fail('Interrupt error without completed discovery. Reboot the working SD image.')
   if any(msg in new for msg in failures):
    s['phase']='unsafe-reboot-required';save(s)
    fail('Driver error during rebind; recovery is NOT verified. State retained. Reboot the working SD image and collect dmesg.')
  rearm_hdmi(s)
  for p in s['consoles']:
   if os.path.exists(p+'/bind'):write(p+'/bind','1')
  if s['eth_was_up']:subprocess.check_call(['ip','link','set','dev','eth0','up'])
  if s.get('networkmanager_active'):subprocess.check_call(['systemctl','start','NetworkManager'])
  nodes=glob.glob('/dev/xillybus_read_32')
  if not nodes:fail('Xillybus read_32 endpoint missing after rebind.')
  s['phase']='rebound-unverified';s['discovery_warning']=warned;save(s)
  save_diagnostics(s)
  os.unlink(STATE)
  print('REBOUND: '+('discovery warning observed; ' if warned else '')+'capture, SSH and HDMI desktop verification still required.')
  print('Check ip -4 addr show eth0 and run the bounded capture test. DHCP/SSH may take time.')
 except (IOError,OSError,RuntimeError,subprocess.CalledProcessError) as e:
  save_diagnostics(s)
  fail('Restore failed: %s. State retained; reboot the working SD image.'%e)
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
