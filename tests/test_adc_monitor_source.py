import importlib.util,math,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
if ROOT.name=='tests':ROOT=ROOT.parent/'scripts'
sys.path.insert(0,str(ROOT))
from test_responsive_monitor import ImmediateWorker
spec=importlib.util.spec_from_file_location('monitor',str(ROOT/'adc_monitor.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
os.environ['MPLBACKEND']='Agg'
class Tests(unittest.TestCase):
 def test_request_does_not_write_during_frame(self):
  with patch.object(m,'control_source',return_value='simulated') as io:
   c=m.SourceController('/dev/test',10)
   c.request('External ADC')
   self.assertEqual(io.call_count,1)
   self.assertEqual(c.source,'simulated')
   io.return_value='external';c.apply_pending()
   self.assertEqual(c.rate,8000000.)
   self.assertEqual(io.call_count,2)
 def test_failed_switch_does_not_claim_success(self):
  with patch.object(m,'control_source',return_value='simulated') as io:
   c=m.SourceController('/dev/test',10);c.request('External ADC')
   io.side_effect=RuntimeError('readback failed')
   with self.assertRaises(RuntimeError):c.apply_pending()
   self.assertEqual(c.source,'simulated')
 def test_gui_switches_both_directions_with_matching_rates(self):
  import matplotlib.pyplot as plt
  from matplotlib.widgets import RadioButtons
  realradio=RadioButtons;radio=[];state=['simulated'];captures=[]
  def control(device,source=None,timeout=10):
   if source is not None:state[0]=source
   return state[0]
  def capture(device,count,timeout):
   captures.append(state[0]);rate=m.SOURCE_RATES[state[0]]
   return [int(1500*math.sin(2*math.pi*1000000*i/rate)) for i in range(count)]
  def make_radio(*args,**kwargs):
   obj=realradio(*args,**kwargs);radio.append(obj);return obj
  def pause(seconds):
   if len(captures)==1:radio[0].set_active(1)
   elif len(captures)==2:radio[0].set_active(0)
   else:
    plt.gcf().savefig('/tmp/adc-monitor-switch-preview.png')
    plt.close('all')
  args=['monitor','--samples','128','--interval','0']
  with patch('matplotlib.pyplot.ion'),patch('receiver_control.read_config',side_effect=RuntimeError('legacy bitstream')),patch.object(sys,'argv',args),patch.dict(os.environ,{'DISPLAY':':test'}),patch.object(m,'control_source',side_effect=control),patch.object(m,'acquire',side_effect=capture),patch('matplotlib.widgets.RadioButtons',side_effect=make_radio),patch.object(m,'CaptureWorker',side_effect=lambda *args:ImmediateWorker(m,*args)),patch.object(m,'pump_gui',side_effect=lambda fig,seconds:pause(seconds)):m.main()
  self.assertEqual(captures,['simulated','external','simulated'])
 def test_csv_never_touches_control_or_capture(self):
  with tempfile.TemporaryDirectory() as d:
   csv=Path(d)/'input.csv';csv.write_text('sample\n'+'\n'.join(str(i) for i in range(64)))
   png=Path(d)/'plot.png'
   with patch.object(sys,'argv',['monitor','--csv',str(csv),'--rate','8000000','--save',str(png)]),patch.object(m,'control_source',side_effect=AssertionError('hardware access')),patch.object(m,'acquire',side_effect=AssertionError('hardware capture')):m.main()
   self.assertTrue(png.exists())
if __name__=='__main__':unittest.main()
