import sys,os,time,math
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts') if Path(__file__).parent.name=='tests' else str(Path(__file__).parent))
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import RadioButtons
from matplotlib.backend_bases import MouseEvent
import adc_monitor as m
import receiver_control as control
initial={'source':'simulated','mode':'iq','tune_phase':control.phase_for_hz(1e6),'sim_phase':control.phase_for_hz(1001000)}
controllers=[];workers=[];radios=[];frames=[];clicks=[];heartbeats=[]
real_controller=control.ReceiverController;real_worker=m.CaptureWorker;real_spectrum=m.frame_spectrum;real_show=plt.show

def new_controller(*args):
 c=real_controller(*args);controllers.append(c);return c

def new_worker(*args):
 w=real_worker(*args);workers.append(w);return w

def radio(*args,**kwargs):
 r=RadioButtons(*args,**kwargs);radios.append(r);return r

def capture(*args):
 time.sleep(.65)
 return [complex(3000*math.cos(2*math.pi*n/8),3000*math.sin(2*math.pi*n/8)) for n in range(4096)]

def spectrum(*args):
 frames.append(dict(controllers[0].settings))
 if len(frames)==2:plt.gcf().canvas.manager.window.after(80,lambda:plt.close('all'))
 return real_spectrum(*args)

def answer(*args,**kwargs):
 clicks.append((time.monotonic(),workers[0].busy,len(frames)))
 return '1000500'

def show(*args,**kwargs):
 real_show(*args,**kwargs)
 fig=plt.gcf();root=fig.canvas.manager.window
 def heartbeat():
  if plt.fignum_exists(fig.number):heartbeats.append(time.monotonic());root.after(20,heartbeat)
 def click():
  assert workers[0].busy and not frames
  started=time.monotonic()
  radios[0].set_active(1)
  ax=fig.axes[5];x,y=ax.transAxes.transform((.5,.5))
  for name in ['button_press_event','button_release_event']:
   event=MouseEvent(name,fig.canvas,x,y,button=1)
   fig.canvas.callbacks.process(name,event)
  assert clicks and clicks[0][0]-started<.15
 root.after(100,click);root.after(10,heartbeat);root.after(4000,lambda:plt.close('all'))

with patch.object(sys,'argv',['monitor','--receiver','--interval','0']),patch.object(control,'read_config',return_value=initial),patch.object(control,'configure',side_effect=lambda device,settings,timeout:dict(settings)),patch.object(control,'ReceiverController',side_effect=new_controller),patch.object(m,'CaptureWorker',side_effect=new_worker),patch.object(m,'acquire_iq',side_effect=capture),patch.object(m,'frame_spectrum',side_effect=spectrum),patch('matplotlib.widgets.RadioButtons',side_effect=radio),patch('tkinter.simpledialog.askstring',side_effect=answer),patch.object(plt,'show',side_effect=show):
 m.main()
assert len(frames)>=2 and clicks[0][1:] == (True,0)
assert frames[0]['source']=='simulated' and frames[0]['tune_phase']==initial['tune_phase']
assert frames[1]['source']=='external' and frames[1]['tune_phase']==control.phase_for_hz(1000500)
assert len(heartbeats)>15
assert not workers[0].process.is_alive()
print('PASS: Tk frequency-button click handled before first capture completed; deferred source/frequency applied to next frame; %d GUI heartbeats; worker stopped'%len(heartbeats))
