import importlib.util
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts' if Path(__file__).parent.name=='tests' else Path(__file__).parent
sys.path.insert(0,str(SCRIPTS))
import receiver_control as control
import adc_monitor as monitor
from test_responsive_monitor import ImmediateWorker

class MemoryDevice:
 def __init__(self):
  self.shadow=bytearray(32);self.committed=bytearray(32);self.committed[3]=control.MARKER;self.pos=0
  self.shadow[4:10]=control.phase_bytes(control.phase_for_hz(1e6));self.shadow[10:16]=self.shadow[4:10];self.commit()
 def commit(self):
  self.committed[0:2]=self.shadow[0:2];self.committed[4:16]=self.shadow[4:16]
 def seek(self,fd,offset,whence):self.pos=offset;return offset
 def write(self,fd,data):
  self.shadow[self.pos:self.pos+len(data)]=data
  if self.pos==2:self.commit()
  self.pos+=len(data);return len(data)
 def read(self,fd,n):
  data=bytes(self.committed[self.pos:self.pos+n]);self.pos+=len(data);return data

class Tests(unittest.TestCase):
 def test_phase_precision_and_limits(self):
  for hz in [0,1,1001000,31999999.999]:
   p=control.phase_for_hz(hz)
   self.assertLess(abs(p*64e6/(1<<48)-hz),2e-7)
   self.assertEqual(control.phase_value(control.phase_bytes(p)),p)
  for hz in [-1,32e6,float('nan'),float('inf')]:
   with self.assertRaises(ValueError):control.phase_for_hz(hz)
 def test_atomic_controls_and_deferred_requests(self):
  dev=MemoryDevice()
  with patch.object(control.os,'open',return_value=100),patch.object(control.os,'close'),patch.object(control.os,'lseek',side_effect=dev.seek),patch.object(control.os,'write',side_effect=dev.write),patch.object(control.os,'read',side_effect=dev.read):
   c=control.ReceiverController('fake',1)
   self.assertEqual(c.mode,'raw');self.assertEqual(c.rate,64e6)
   c.request('External ADC');c.request_mode('DDC I/Q');c.request_frequency('tune',1002000);c.request_frequency('sim',1003000)
   self.assertEqual(c.source,'simulated');self.assertEqual(c.frequency('tune'),1e6)
   c.apply_pending()
   self.assertEqual(c.source,'external');self.assertEqual(c.rate,8000)
   self.assertAlmostEqual(c.frequency('sim'),1003000,places=5)
   self.assertEqual(c.settings,control.read_config('fake',1))
 def test_iq_signed_pairs_and_short_frame(self):
  with tempfile.NamedTemporaryFile() as f:
   f.write(struct.pack('<4i',-8388608,8388607,123,-456));f.flush()
   self.assertEqual(monitor.acquire_iq(f.name,2,1),[complex(-8388608,8388607),complex(123,-456)])
   with self.assertRaises(RuntimeError):monitor.acquire_iq(f.name,3,1)
 def test_no_ddc_marker(self):
  with tempfile.NamedTemporaryFile() as f:
   f.write(bytes(32));f.flush()
   with self.assertRaises(RuntimeError):control.read_config(f.name,1)

 def test_monitor_mode_and_source_controls(self):
  os.environ['MPLBACKEND']='Agg'
  import matplotlib.pyplot as plt
  from matplotlib.widgets import RadioButtons
  radios=[];captures=[];instances=[]
  initial={'source':'simulated','mode':'raw','tune_phase':control.phase_for_hz(1e6),'sim_phase':control.phase_for_hz(1e6)}
  real_controller=control.ReceiverController
  hardware=[dict(initial)]
  def configure(device,settings,timeout):hardware[0]=dict(settings);return dict(settings)
  def factory(*args):
   c=real_controller(*args);instances.append(c);return c
  def radio(*args,**kwargs):
   r=RadioButtons(*args,**kwargs);radios.append(r);return r
  def raw(*args):
   captures.append(('raw',hardware[0]['source']));return [0]*4096
  def iq(*args):
   captures.append(('iq',hardware[0]['source']));return [complex(100,100)]*4096
  def pause(*args):
   if len(captures)==1:
    radios[0].set_active(1);radios[1].set_active(1);instances[0].request_frequency('sim',1001000)
   else:plt.close('all')
  with patch('matplotlib.pyplot.ion'),patch.object(sys,'argv',['monitor','--receiver','--interval','0']),patch.dict(os.environ,{'DISPLAY':':test'}),patch.object(control,'read_config',return_value=initial),patch.object(control,'configure',side_effect=configure),patch.object(control,'ReceiverController',side_effect=factory),patch.object(monitor,'acquire',side_effect=raw),patch.object(monitor,'acquire_iq',side_effect=iq),patch('matplotlib.widgets.RadioButtons',side_effect=radio),patch.object(monitor,'CaptureWorker',side_effect=lambda *args:ImmediateWorker(monitor,*args)),patch.object(monitor,'pump_gui',side_effect=lambda fig,seconds:pause(seconds)):
   monitor.main()
  self.assertEqual(captures,[('raw','simulated'),('iq','external')])
  self.assertAlmostEqual(instances[0].frequency('sim'),1001000,places=5)

if __name__=='__main__':unittest.main()
