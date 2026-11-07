import os,sys,unittest,tempfile,struct,wave,math
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import receiver_control as c
import adc_monitor as m
import capture_ssb_audio as recording
from test_receiver_control import MemoryDevice
os.environ.setdefault('MPLBACKEND','Agg')

class Tests(unittest.TestCase):
 def test_new_modes_atomic_and_legacy_rejection(self):
  d=MemoryDevice();d.committed[3]=c.SSB_MARKER
  patches=[patch.object(c.os,'open',return_value=100),patch.object(c.os,'close'),patch.object(c.os,'lseek',side_effect=d.seek),patch.object(c.os,'read',side_effect=d.read),patch.object(c.os,'write',side_effect=d.write)]
  for p in patches:p.start()
  try:
   ctl=c.ReceiverController('fake',1,mode='usb');self.assertEqual(ctl.mode,'usb');self.assertEqual(ctl.rate,8000)
   ctl.request_mode('LSB audio');self.assertEqual(ctl.mode,'usb');ctl.apply_pending();self.assertEqual(ctl.mode,'lsb')
   ctl.request_mode('DDC I/Q');ctl.apply_pending();self.assertEqual(ctl.mode,'iq')
   d.committed[3]=c.MARKER
   ctl.request_mode('USB audio')
   with patch.object(c.os,'write') as write:
    with self.assertRaisesRegex(RuntimeError,'SSB bitstream'):ctl.apply_pending()
    write.assert_not_called()
  finally:
   for p in reversed(patches):p.stop()
 def test_audio_words_and_wav_scaling(self):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/'audio.bin';f.write_bytes(struct.pack('<5i',-8388608,-100,0,100,8388607))
   self.assertEqual(m.acquire_audio(str(f),5,1),[-8388608,-100,0,100,8388607])
   with self.assertRaises(RuntimeError):m.acquire_audio(str(f),6,1)
   f.write_bytes(struct.pack('<i',8388608))
   with self.assertRaises(RuntimeError):m.acquire_audio(str(f),1,1)
   wav=Path(td)/'audio.wav';m.write_audio_wav(wav,[-100000,0,100000])
   with wave.open(str(wav),'rb') as w:
    self.assertEqual((w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes()),(1,2,8000,3))
    self.assertEqual(struct.unpack('<3h',w.readframes(3)),(-32768,0,32767))
 def test_audio_plot_units_and_spectrum(self):
  import matplotlib.pyplot as plt
  values=[3000*math.sin(2*math.pi*1000*n/8000) for n in range(4096)]
  self.assertEqual(m.frame_spectrum(values,False,8000,True)[4],1000)
  fig,axes=plt.subplots(3,1)
  try:
   plot=m.MonitorPlot(fig,axes,enable_blit=False);plot.configure(False,8000,True)
   self.assertIn('audio',axes[0].get_title().lower());self.assertEqual(axes[1].get_xlim(),(0,4))
   self.assertFalse(plot.line_q.get_visible());self.assertEqual(axes[0].get_xlabel(),'Time (ms)')
  finally:plt.close(fig)
 def test_continuous_wav_fragments_and_overflow(self):
  class Controller:mode='usb'
  raw=struct.pack('<4h',-32768,-1,1,32767)
  for overflow in (0,1):
   with tempfile.TemporaryDirectory() as td:
    f=Path(td)/'record.wav';parts=iter([raw[:3],raw[3:4],raw[4:]])
    with patch.object(sys,'argv',['capture',str(f),'--seconds','0.0005']),patch.object(recording,'ReceiverController',return_value=Controller()),patch.object(recording,'_read_bytes',return_value=bytes([0,0,0,0xd3]+[0]*12)),patch.object(recording,'read_audio_status',return_value=bytes([overflow])),patch.object(recording.os,'open',return_value=100),patch.object(recording.os,'read',side_effect=lambda *a:next(parts)),patch.object(recording.os,'close') as close:
     if overflow:
      with self.assertRaisesRegex(RuntimeError,'overflow'):recording.main()
     else:recording.main()
     close.assert_called_once_with(100)
    with wave.open(str(f),'rb') as w:self.assertEqual(w.readframes(4),raw);self.assertEqual(w.getnframes(),4)
 def test_monitor_audio_capture_render(self):
  with tempfile.TemporaryDirectory() as td:
   image=Path(td)/'usb.png'
   settings={'source':'simulated','mode':'usb','tune_phase':c.phase_for_hz(1e6),'sim_phase':c.phase_for_hz(1001000)}
   values=[int(3000*math.sin(2*math.pi*n/8)) for n in range(4096)]
   with patch.object(sys,'argv',['monitor','--receiver','--mode','usb','--save',str(image)]),patch.object(c,'read_config',return_value=settings),patch.object(c,'configure',side_effect=lambda device,state,timeout:dict(state)),patch.object(m,'acquire_audio',return_value=values) as audio,patch.object(m,'acquire') as raw,patch.object(m,'acquire_iq') as iq:
    m.main();self.assertEqual(audio.call_count,1);raw.assert_not_called();iq.assert_not_called()
   self.assertGreater(image.stat().st_size,10000)
 def test_python35_syntax(self):
  import ast
  for name in ['adc_monitor.py','receiver_control.py','capture_ssb_audio.py']:
   source=(Path(__file__).resolve().parents[1]/'scripts'/name).read_text()
   if sys.version_info >= (3,8):
    ast.parse(source,feature_version=(3,5))
   else:
    # On Xillinux the native Python 3.5 parser checks compatibility directly.
    ast.parse(source)

if __name__=='__main__':unittest.main()
