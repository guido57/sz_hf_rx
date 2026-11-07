import importlib.util,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('ctl',str(Path(__file__).resolve().parents[1]/'scripts'/'jtag_lifecycle.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Clock:
 def __init__(self):self.now=0
 def monotonic(self):return self.now
 def sleep(self,t):self.now+=t
class Port:
 def __init__(self,levels):self.levels=list(levels);self.last=self.levels[-1]
 def read(self,offset):
  if self.levels:self.last=self.levels.pop(0)
  return self.last
class Tests(unittest.TestCase):
 def setUp(self):self.oldtime=m.time;self.oldreg=m.RegisterPage;self.oldfb=m.framebuffer_info;self.oldprofile=m.hardware_profile;self.oldsave=m.save;m.time=Clock()
 def tearDown(self):m.time=self.oldtime;m.RegisterPage=self.oldreg;m.framebuffer_info=self.oldfb;m.hardware_profile=self.oldprofile;m.save=self.oldsave
 def test_drain_waits_for_continuous_quiet(self):
  m.wait_empty(Port([0,0,4,0,0,0,0,0,0,0,0,0,0,0]))
  self.assertGreaterEqual(m.time.now,.13)
 def test_stuck_port_refuses_programming(self):
  with self.assertRaisesRegex(RuntimeError,'DO NOT program JTAG'):m.wait_empty(Port([7]),timeout=.2)
 def test_rearm_uses_current_allocation_and_preserves_hp_bits(self):
  events=[]
  class Reg:
   def __init__(self,addr):self.addr=addr
   def read(self,off):return {0:0xa,0x14:0xf00}.get(off,0)
   def write(self,off,value):events.append((self.addr,off,value))
   def close(self):pass
  m.RegisterPage=Reg;m.hardware_profile=lambda:None;m.save=lambda s:None
  info={'physical':0x1ea00000,'width':1024,'height':768}
  m.framebuffer_info=lambda:info
  state={'hdmi_before':{'physical':0x1e800000}}
  m.rearm_hdmi(state)
  self.assertEqual([e[1:] for e in events if e[0]==m.VGA_BASE],[(8,0),(16,0x1ea00000),(12,49152),(8,1)])
  self.assertIn((m.HP2_BASE,0,0xb),events);self.assertIn((m.HP2_BASE,0x14,0xf01),events)
  self.assertEqual(state['hdmi_after'],info)
 def test_stuck_rearm_never_enables_display(self):
  events=[]
  class Reg:
   def __init__(self,addr):self.addr=addr
   def read(self,off):return 7 if off==0xc else 0
   def write(self,off,value):events.append((self.addr,off,value))
   def close(self):pass
  m.RegisterPage=Reg;m.hardware_profile=lambda:None;m.save=lambda s:None
  m.framebuffer_info=lambda:{'physical':0x1ea00000,'width':1024,'height':768}
  with self.assertRaises(RuntimeError):m.rearm_hdmi({})
  self.assertNotIn((m.VGA_BASE,8,1),events)
if __name__=='__main__':unittest.main()
