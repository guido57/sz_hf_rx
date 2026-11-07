import os,sys,time,unittest,tempfile,multiprocessing
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts') if Path(__file__).parent.name=='tests' else str(Path(__file__).parent))
import adc_monitor as m
import receiver_control as control
os.environ.setdefault('MPLBACKEND','Agg')

def controller():
 c=object.__new__(control.ReceiverController)
 c.device='fake';c.timeout=2;c.pending={}
 c.settings={'source':'simulated','mode':'iq','tune_phase':control.phase_for_hz(1e6),'sim_phase':control.phase_for_hz(1001000)}
 return c

def receive(worker,timeout=3):
 until=time.monotonic()+timeout
 while time.monotonic()<until:
  result=worker.poll()
  if result is not None:return result
  time.sleep(.01)
 raise AssertionError('Worker did not return a frame')

class Tests(unittest.TestCase):
 def test_silence_and_dc_carrier(self):
  self.assertIsNone(m.frame_spectrum([0j]*64,True,8000)[4])
  self.assertIsNone(m.frame_spectrum([10]*64,False,64e6)[4])
  self.assertEqual(m.frame_spectrum([10+3j]*64,True,8000)[4],0.)
 def test_worker_keeps_capture_off_gui_and_commits_between_frames(self):
  c=controller();events=multiprocessing.get_context('fork').Queue()
  def capture(*args):
   events.put('open');time.sleep(.3);events.put('close');return [1+2j]*8
  def configure(*args):events.put('configure');return args[1]
  with patch.object(m,'acquire_iq',side_effect=capture),patch.object(control,'configure',side_effect=configure):
   worker=m.CaptureWorker(c,True,'fake',8,2)
   try:
    worker.submit(m.capture_state(c,True))
    self.assertEqual(events.get(timeout=1),'open')
    start=time.monotonic();c.request('External ADC')
    self.assertIsNone(worker.poll())
    self.assertLess(time.monotonic()-start,.1)
    self.assertEqual(c.source,'simulated')
    state,values=receive(worker);self.assertEqual(state['source'],'simulated')
    self.assertEqual(events.get(timeout=1),'close')
    worker.submit(m.capture_state(c,True))
    self.assertEqual(events.get(timeout=1),'configure')
    self.assertEqual(events.get(timeout=1),'open')
    state,values=receive(worker);self.assertEqual(state['source'],'external')
    self.assertEqual(events.get(timeout=1),'close')
   finally:worker.close();events.close()
 def test_worker_deadline_and_close(self):
  with tempfile.TemporaryDirectory() as d:
   fifo=os.path.join(d,'blocked');os.mkfifo(fifo)
   worker=m.CaptureWorker(None,False,fifo,8,1)
   try:
    worker.submit(None)
    with self.assertRaisesRegex(RuntimeError,'timed out'):receive(worker)
   finally:worker.close()
   self.assertFalse(worker.process.is_alive())
 def test_closing_during_capture_is_bounded(self):
  def blocked(*args):time.sleep(10)
  with patch.object(m,'acquire',side_effect=blocked):
   worker=m.CaptureWorker(None,False,'fake',8,20)
   worker.submit(None);time.sleep(.04);start=time.monotonic();worker.close()
   self.assertLess(time.monotonic()-start,1.)
   self.assertFalse(worker.process.is_alive())
 def test_plot_reuses_artists_and_repaints_after_resize(self):
  import matplotlib.pyplot as plt
  fig,axes=plt.subplots(3,1)
  try:
   plot=m.MonitorPlot(fig,axes);plot.configure(True,8000)
   plot.line_i.set_data([0,1],[1,2]);plot.title.set_text('Frame 1');plot.paint()
   line=plot.line_i;bars=tuple(plot.bars)
   with patch.object(fig.canvas,'draw',wraps=fig.canvas.draw) as draw:
    plot.configure(True,8000);plot.line_i.set_data([0,1],[2,3]);plot.paint()
    self.assertEqual(draw.call_count,0)
    plot.invalidate();plot.paint();self.assertGreater(draw.call_count,0)
   self.assertIs(line,plot.line_i);self.assertEqual(bars,tuple(plot.bars))
   plot.configure(False,64e6);plot.paint();self.assertFalse(plot.line_q.get_visible())
  finally:plt.close(fig)


class ImmediateWorker(object):
 """Deterministic transport for GUI state tests; real-process tests are above."""
 def __init__(self,module,controller,receiver,device,count,timeout):
  self.module=module;self.controller=controller;self.receiver=receiver
  self.device=device;self.count=count;self.timeout=timeout;self.busy=False
  self.applied=dict(controller.settings) if receiver else {'source':controller.source}
 def submit(self,state):
  if state!=self.applied:
   if self.receiver:control.configure(self.controller.device,state,self.timeout)
   else:self.module.control_source(self.controller.device,state['source'],self.timeout)
   self.applied=dict(state)
  iq=self.receiver and state['mode']=='iq'
  func=self.module.acquire_iq if iq else self.module.acquire
  self.result=(dict(state),func(self.device,self.count,self.timeout));self.busy=True
 def poll(self):self.busy=False;return self.result
 def close(self):pass

if __name__=='__main__':unittest.main()
