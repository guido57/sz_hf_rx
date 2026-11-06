#!/usr/bin/env python3
"""Matplotlib raw ADC / complex DDC snapshot monitor; Python 3.5+."""
from __future__ import print_function
import argparse,os,struct,signal,csv,math,time,sys

def acquire(device,count,timeout):
 def expired(signum,frame):raise RuntimeError('Capture timed out; check bitstream/driver and other readers')
 old=signal.signal(signal.SIGALRM,expired);signal.alarm(timeout);fd=None
 try:
  fd=os.open(device,os.O_RDONLY);raw=b''
  while len(raw)<count*4:
   b=os.read(fd,count*4-len(raw))
   if not b:raise RuntimeError('Short frame: %d of %d bytes'%(len(raw),count*4))
   raw+=b
  values=[]
  for i,w in enumerate(struct.unpack('<%dI'%count,raw)):
   if w>>16!=i:raise RuntimeError('Index mismatch at word %d: received %d'%(i,w>>16))
   v=w&65535;v=v-65536 if v&32768 else v
   if v < -8192 or v>8191:raise RuntimeError('Not a sign-extended 14-bit ADC frame')
   values.append(v)
  return values
 finally:
  if fd is not None:os.close(fd)
  signal.alarm(0);signal.signal(signal.SIGALRM,old)

def acquire_iq(device,count,timeout):
 from receiver_control import deadline
 with deadline(timeout):
  fd=os.open(device,os.O_RDONLY)
  try:
   raw=b''
   while len(raw)<count*8:
    part=os.read(fd,count*8-len(raw))
    if not part:raise RuntimeError('Short I/Q snapshot')
    raw+=part
   words=struct.unpack('<%di'%(count*2),raw)
   if any(v<-(1<<23) or v>=(1<<23) for v in words):raise RuntimeError('Invalid signed 24-bit I/Q stream')
   return [complex(words[i],words[i+1]) for i in range(0,len(words),2)]
  finally:os.close(fd)

def acquire_audio(device,count,timeout):
 from receiver_control import deadline
 with deadline(timeout):
  fd=os.open(device,os.O_RDONLY)
  try:
   raw=b''
   while len(raw)<count*4:
    part=os.read(fd,count*4-len(raw))
    if not part:raise RuntimeError('Short mono audio snapshot')
    raw+=part
   words=struct.unpack('<%di'%count,raw)
   if any(v<-(1<<23) or v>=(1<<23) for v in words):raise RuntimeError('Invalid signed 24-bit audio stream')
   return list(words)
  finally:os.close(fd)

def write_audio_wav(path,values):
 """One finite 8 kHz mono snapshot, fixed input-referred PCM16 scaling."""
 import wave
 gain=(2.0/(1000./1024.)**3)*32767./8192.
 pcm=[max(-32768,min(32767,int(round(v*gain)))) for v in values]
 with wave.open(str(path),'wb') as wav:
  wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000)
  wav.writeframes(struct.pack('<%dh'%len(pcm),*pcm))

SOURCE_RATES={'simulated':64000000.,'external':8000000.}
SOURCE_LABELS={'simulated':'Simulated ADC','external':'External ADC'}

def control_source(device,source=None,timeout=10):
 def expired(signum,frame):raise RuntimeError('ADC source control timed out; check bitstream/driver')
 old=signal.signal(signal.SIGALRM,expired);signal.alarm(timeout);fd=None
 try:
  fd=os.open(device,os.O_RDWR)
  if source is not None:
   os.lseek(fd,0,os.SEEK_SET)
   if os.write(fd,bytes([int(source=='external')]))!=1:raise RuntimeError('Short ADC source write')
  os.lseek(fd,0,os.SEEK_SET);value=os.read(fd,1)
  if len(value)!=1:raise RuntimeError('Short ADC source read')
  selected='external' if value[0]&1 else 'simulated'
  if source is not None and selected!=source:raise RuntimeError('ADC source readback mismatch')
  return selected
 finally:
  try:
   if fd is not None:os.close(fd)
  finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)

class SourceController(object):
 """Queue GUI requests; hardware writes happen only between closed frames."""
 def __init__(self,device,timeout,source=None):
  self.device=device;self.timeout=timeout;self.pending=None
  self.source=control_source(device,source,timeout)
 @property
 def rate(self):return SOURCE_RATES[self.source]
 def request(self,label):
  self.pending=next(key for key,value in SOURCE_LABELS.items() if value==label)
 def apply_pending(self):
  if self.pending is not None:
   requested=self.pending
   selected=control_source(self.device,requested,self.timeout)
   self.source=selected;self.pending=None


def capture_state(controller,receiver):
 """Consume queued GUI requests without performing hardware I/O."""
 if controller is None:return None
 if receiver:
  state=dict(controller.settings);state.update(controller.pending);controller.pending.clear()
 else:
  state={'source':controller.pending or controller.source};controller.pending=None
 return state

def _capture_worker(commands,results,controller,receiver,device,count,timeout):
 # A process, rather than a thread: signal-based I/O deadlines remain usable.
 signal.signal(signal.SIGINT,signal.SIG_IGN)
 applied=dict(controller.settings) if receiver else ({'source':controller.source} if controller else None)
 while True:
  state=commands.get()
  if state=='stop':return
  try:
   if controller is not None and state!=applied:
    if receiver:
     from receiver_control import configure
     configure(controller.device,state,timeout)
    else:control_source(controller.device,state['source'],timeout)
    applied=dict(state)
   iq=receiver and state['mode']=='iq'
   audio=receiver and state['mode'] in ('usb','lsb')
   values=acquire_iq(device,count,timeout) if iq else (acquire_audio(device,count,timeout) if audio else acquire(device,count,timeout))
   results.put((state,values,None))
  except Exception as error:
   results.put((state,None,str(error)));return

class CaptureWorker(object):
 """At most one capture in flight; no stale-frame queue and one device reader."""
 def __init__(self,controller,receiver,device,count,timeout):
  import multiprocessing
  context=multiprocessing.get_context('fork')
  self.commands=context.Queue(1);self.results=context.Queue(1)
  self.process=context.Process(target=_capture_worker,args=(self.commands,self.results,controller,receiver,device,count,timeout))
  self.process.daemon=True;self.process.start();self.busy=False
 def submit(self,state):
  if self.busy:raise RuntimeError('A capture is already running')
  self.commands.put(state);self.busy=True
 def poll(self):
  from queue import Empty
  try:result=self.results.get_nowait()
  except Empty:
   if not self.process.is_alive():raise RuntimeError('Capture process stopped unexpectedly')
   return None
  self.busy=False
  if result[2] is not None:raise RuntimeError(result[2])
  return result[:2]
 def close(self):
  if self.process.is_alive():self.process.terminate()
  self.process.join(.5)
  self.commands.close();self.results.close()

def frame_spectrum(values,iq,rate,audio=False):
 import numpy as np
 y=np.asarray(values,dtype=complex if iq else float)
 if iq or audio:y=y*(2.0/(1000./1024.)**3)
 ac=y if iq else y-y.mean();n=len(y);win=np.hanning(n)
 if iq:
  mag=np.abs(np.fft.fftshift(np.fft.fft(ac*win)))/sum(win)
  freq=np.fft.fftshift(np.fft.fftfreq(n,1/rate))
 else:
  mag=2*np.abs(np.fft.rfft(ac*win))/sum(win);mag[0]/=2
  if n%2==0:mag[-1]/=2
  freq=np.fft.rfftfreq(n,1/rate)
 # Silence has no dominant frequency; do not report the first (-4 kHz) bin.
 dominant=float(freq[int(np.argmax(mag))]) if np.any(np.abs(ac)>0) else None
 return y,ac,freq,mag,dominant

def pump_gui(fig,seconds=.03):
 # Unlike pyplot.pause, this does not force a full draw for widget changes.
 fig.canvas.start_event_loop(seconds)

class MonitorPlot(object):
 """Reuse artists; blit changing data without repainting ticks and controls."""
 def __init__(self,fig,axes,status=None,enable_blit=True):
  self.fig=fig;self.axes=axes;self.status=status;self.mode=None;self.backgrounds=None
  self.blit=enable_blit and bool(getattr(fig.canvas,'supports_blit',False))
  self.title=fig.suptitle('',fontsize=10);self.title.set_animated(self.blit)
  if status is not None:status.set_animated(self.blit)
  self.artists=[];self.header_box=None;self.status_box=None
  fig.canvas.mpl_connect('draw_event',self.on_draw)
  fig.canvas.mpl_connect('resize_event',self.invalidate)

 def invalidate(self,event=None):self.backgrounds=None

 def on_draw(self,event):
  if not self.blit or not self.artists:return
  from matplotlib.transforms import Bbox
  b=self.fig.bbox;x,y,w,h=b.bounds
  self.header_box=Bbox.from_bounds(x,y+.90*h,w,.10*h)
  self.backgrounds=[self.fig.canvas.copy_from_bbox(ax.bbox) for ax in self.axes]
  self.header_bg=self.fig.canvas.copy_from_bbox(self.header_box)
  if self.status is not None:
   sx,sy=self.status.get_position()
   self.status_box=Bbox.from_bounds(x+(sx-.01)*w,y+(sy-.02)*h,(.99-sx)*w,.055*h)
   self.status_bg=self.fig.canvas.copy_from_bbox(self.status_box)
  self.paint()

 def paint(self):
  if not self.blit:
   self.fig.canvas.draw_idle();return
  if self.backgrounds is None:
   self.fig.canvas.draw();return
  c=self.fig.canvas
  for ax,bg,artists in zip(self.axes,self.backgrounds,self.artists):
   c.restore_region(bg)
   for artist in artists:
    if artist.get_visible():ax.draw_artist(artist)
   c.blit(ax.bbox)
  c.restore_region(self.header_bg);self.fig.draw_artist(self.title);c.blit(self.header_box)
  self.paint_status()

 def paint_status(self):
  if self.status is None:return
  if self.blit and self.backgrounds is not None:
   self.fig.canvas.restore_region(self.status_bg);self.fig.draw_artist(self.status);self.fig.canvas.blit(self.status_box)
  else:self.fig.canvas.draw_idle()

 def set_status(self,text):
  if self.status is not None:self.status.set_text(text);self.paint_status()

 def configure(self,iq,rate,audio=False):
  if self.mode==(iq,rate,audio):return
  self.mode=(iq,rate,audio);self.backgrounds=None
  for ax in self.axes:ax.clear();ax.grid(alpha=.25)
  a,b,c=self.axes
  self.line_i,=a.plot([],[],'.-',markersize=2,linewidth=.8,label='I' if iq else ('Audio' if audio else 'ADC'),animated=self.blit)
  self.line_q,=a.plot([],[],linewidth=.8,label='Q',animated=self.blit);self.line_q.set_visible(iq)
  if iq:a.legend(loc='upper right')
  a.set_title('DDC complex envelope (input-referred)' if iq else ('SSB demodulated audio (input-referred)' if audio else 'Raw signed samples'))
  a.set_xlabel('Time (ms)' if iq or audio else 'Time (us)');a.set_ylabel('ADC code');a.set_ylim(-8500,8500)
  self.spectrum,=b.plot([],[],linewidth=.8,animated=self.blit)
  b.set_title('Complex spectrum: Hann window, DC retained' if iq else 'Spectrum: Hann window, DC removed')
  b.set_xlabel('Offset from tuned frequency (kHz)' if iq else ('Audio frequency (kHz)' if audio else 'Frequency (MHz)'));b.set_ylabel('Peak dBFS')
  b.set_xlim((-4,4) if iq else ((0,4) if audio else (0,rate/2e6)));b.set_ylim(-120,3)
  self.bars=c.barh([0,1],[0,0],color=['steelblue','darkorange'])
  for bar in self.bars:bar.set_animated(self.blit)
  c.set_yticks([0,1]);c.set_yticklabels(['Peak','RMS' if iq else 'AC RMS']);c.set_xlim(0,103)
  c.set_xticks([0,20,40,60,80,100]);c.set_xticklabels(['-100','-80','-60','-40','-20','0'])
  c.set_xlabel('Input-referred dBFS (complex envelope)' if iq else 'dBFS (RMS uses full-scale sine reference)')
  self.artists=[[self.line_i,self.line_q],[self.spectrum],list(self.bars)]

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--device',default='/dev/xillybus_read_32')
 p.add_argument('--samples',type=int,default=4096)
 p.add_argument('--receiver',action='store_true',help='require the new DDC receiver bitstream')
 p.add_argument('--mode',choices=['raw','iq','usb','lsb'],help='raw ADC or 8 ksample/s complex DDC')
 p.add_argument('--tune',type=float,help='DDC tuning frequency in Hz')
 p.add_argument('--sim-frequency',type=float,help='simulator carrier frequency in Hz')
 p.add_argument('--rate',type=float,help='sample rate for CSV/legacy mode; receiver uses 64 MS/s raw or 8 ksample/s I/Q')
 p.add_argument('--control-device',default='/dev/xillybus_mem_8')
 p.add_argument('--source',choices=['auto','simulated','external'],default='auto',help='initial source; auto reads the FPGA setting')
 p.add_argument('--no-source-control',action='store_true',help='legacy bitstream: no source selector, use --rate')
 p.add_argument('--timeout',type=int,default=10)
 p.add_argument('--interval',type=float,default=.5)
 p.add_argument('--wave-us',type=float,default=4.,help='waveform time span in microseconds')
 p.add_argument('--once',action='store_true',help='one frame; leave window open')
 p.add_argument('--save',help='save one PNG/PDF instead of opening a window')
 p.add_argument('--csv',help='plot an existing CSV instead of reading hardware')
 a=p.parse_args()
 if (a.rate is not None and a.rate<=0) or a.samples<8 or a.samples>65536 or a.timeout<1 or a.interval<0 or a.wave_us<=0:p.error('Invalid capture parameters')
 import matplotlib
 if a.save:matplotlib.use('Agg')
 elif not os.environ.get('DISPLAY'):p.error('No graphical display: startx on HDMI, use DISPLAY=:0, or use --save')
 import numpy as np
 import matplotlib.pyplot as plt
 cached=None
 if a.csv:
  with open(a.csv) as f:rows=list(csv.DictReader(f))
  cached=[int(r['sample']) for r in rows]
  if len(cached)<8:raise RuntimeError('CSV must contain at least eight samples')
 controller=None
 receiver=False
 if cached is None and not a.no_source_control:
  # Explicit --receiver is recommended. Auto-detect only the new marker;
  # legacy source/rate behavior remains available for the tested ADC design.
  from receiver_control import ReceiverController,read_config
  try:
   read_config(a.control_device,a.timeout);receiver=True
  except RuntimeError:
   if a.receiver:raise
  if receiver:
   if a.samples!=4096:p.error('Receiver snapshots contain exactly 4096 samples/pairs')
   controller=ReceiverController(a.control_device,a.timeout,None if a.source=='auto' else a.source,a.mode,a.tune,a.sim_frequency)
  else:
   if a.mode is not None or a.tune is not None or a.sim_frequency is not None:p.error('Frequency and mode controls require the DDC bitstream')
   controller=SourceController(a.control_device,a.timeout,None if a.source=='auto' else a.source)
  if a.rate is not None and a.rate!=controller.rate:
   p.error('--rate does not match selected source; omit --rate for automatic selection')
  a.rate=controller.rate
 else:
  if a.source!='auto':p.error('--source requires live source control')
  if a.rate is None:a.rate=64000000.
 worker=CaptureWorker(controller,receiver,a.device,a.samples,a.timeout) if cached is None and not a.save and not a.once else None
 fig,axes=plt.subplots(3,1,figsize=(10,8))
 status=None

 def redraw_widget(ax):
  if plot.blit:fig.draw_artist(ax);fig.canvas.blit(ax.bbox)
  else:fig.canvas.draw_idle()

 switching=controller is not None and not a.save and not a.once
 fig.subplots_adjust(hspace=.65,top=.84,bottom=.25 if switching and receiver else (.20 if switching else .07))
 if switching:
  from matplotlib.widgets import RadioButtons
  selector_axes=fig.add_axes([.12,.015,.30,.105])
  labels=[SOURCE_LABELS['simulated'],SOURCE_LABELS['external']]
  selector=RadioButtons(selector_axes,labels,active=int(controller.source=='external'));selector.drawon=False
  status=fig.text(.46,.06,'Select ADC source; rate follows automatically.',fontsize=9)
  def select_source(label):
   controller.request(label)
   plot.set_status('Requested '+label+'; applying after current capture.')
   redraw_widget(selector_axes)
  selector.on_clicked(select_source)
  if receiver:
   from matplotlib.widgets import Button
   mode_axes=fig.add_axes([.43,.015,.20,.105])
   from receiver_control import MODE_LABELS
   mode_selector=RadioButtons(mode_axes,MODE_LABELS,active=['raw','iq','usb','lsb'].index(controller.mode))
   mode_selector.drawon=False
   def select_mode(label):
    controller.request_mode(label);plot.set_status('Requested '+label+'; applying after current capture.')
    redraw_widget(mode_axes)
   mode_selector.on_clicked(select_mode)
   tune_button=Button(fig.add_axes([.67,.07,.28,.04]),'Tune frequency (Hz)')
   sim_button=Button(fig.add_axes([.67,.015,.28,.04]),'Simulator frequency (Hz)')
   tune_button.drawon=False;sim_button.drawon=False
   # Ubuntu 16.04 has Matplotlib 1.5, predating its TextBox widget.
   def edit_frequency(name):
    from tkinter import simpledialog
    text=simpledialog.askstring('Receiver frequency','Enter frequency in Hz (0 <= f < 32000000):',initialvalue='%.3f'%controller.frequency(name),parent=fig.canvas.manager.window)
    if text is not None:
     try:controller.request_frequency(name,float(text));plot.set_status('Frequency queued for next capture')
     except ValueError as e:plot.set_status(str(e))
   tune_button.on_clicked(lambda event:edit_frequency('tune'))
   sim_button.on_clicked(lambda event:edit_frequency('sim'))
   status.set_position((.12,.16))

 try:fig.canvas.manager.set_window_title('Xillinux ADC monitor')
 except AttributeError:
  try:fig.canvas.set_window_title('Xillinux ADC monitor')
  except AttributeError:pass
 plot=MonitorPlot(fig,axes,status,enable_blit=not a.save)
 plot.configure(receiver and controller.mode=='iq',a.rate,receiver and controller.mode in ('usb','lsb'))
 plot.title.set_text('Waiting for first capture')
 plot.paint()
 frames=0
 def render(values):
  iq=receiver and controller.mode=='iq'
  audio=receiver and controller.mode in ('usb','lsb')
  baseband=iq or audio
  y,ac,freq,mag,dominant=frame_spectrum(values,iq,a.rate,audio);n=len(y)
  mean=abs(y.mean()) if iq else float(y.mean())
  rms=float(np.sqrt(np.mean(np.abs(ac)**2)));peak=float(np.max(np.abs(y)))
  peak_db=20*math.log10(peak/8192.) if peak else float('-inf')
  # RMS dBFS referenced to the RMS of a full-scale sine, excluding DC.
  rms_db=20*math.log10(rms/(8192. if iq else 8192./math.sqrt(2))) if rms else float('-inf')
  rails=0 if iq or audio else int(np.count_nonzero((y<=-8192)|(y>=8191)))
  plot_y=y.real if iq else y
  plot.configure(iq,a.rate,audio)
  limit=min(n,max(2,int((.025 if baseband else a.wave_us*1e-6)*a.rate)))
  x=np.arange(limit)/a.rate*(1e3 if baseband else 1e6)
  plot.line_i.set_data(x,plot_y[:limit]);plot.line_q.set_data(x,y.imag[:limit] if iq else np.zeros(limit))
  # Waveform limits only change with mode/rate/span, not with every frame.
  span=(float(x[0]),float(x[-1]))
  if tuple(axes[0].get_xlim())!=span:axes[0].set_xlim(span);plot.invalidate()
  plot.spectrum.set_data(freq/(1e3 if baseband else 1e6),20*np.log10(np.maximum(mag/8192.,1e-12)))
  for bar,level in zip(plot.bars,[peak_db,rms_db]):bar.set_width(100+max(-100,level))
  rate_text='%.3f ksample/s I/Q'%(a.rate/1e3) if iq else ('8.000 ksample/s audio' if audio else '%.3f MS/s'%(a.rate/1e6))
  dominant_text='No signal' if dominant is None else ('%.1f Hz'%dominant if baseband else '%.3f MHz'%(dominant/1e6))
  title='Frame %d | %d samples | %s | peak %.2f dBFS | RMS %.2f dBFS\nmin %d | max %d | DC %.2f | dominant bin %s | rail codes %d'%(frames,n,rate_text,peak_db,rms_db,min(plot_y),max(plot_y),mean,dominant_text,rails)
  title=('Live '+SOURCE_LABELS[controller.source]+' | ' if controller is not None else ('CSV playback | ' if cached is not None else 'Live capture | '))+title
  if receiver:title+='\nTune %.3f Hz | Simulator %.3f Hz | %s'%(controller.frequency('tune'),controller.frequency('sim'),controller.mode.upper())
  plot.title.set_text(title)
  print('Frame %d: min=%d max=%d DC=%.2f AC_RMS=%.2f peak=%.2f dBFS dominant=%s rail_codes=%d'%(frames,min(plot_y),max(plot_y),mean,rms,peak_db,dominant_text,rails))
  sys.stdout.flush();plot.paint()

 if not a.save:plt.ion();plt.show()
 try:
  next_capture=0.
  while a.save or plt.fignum_exists(fig.number):
   if worker is not None:
    if not worker.busy and time.monotonic()>=next_capture:
     worker.submit(capture_state(controller,receiver))
    result=worker.poll() if worker.busy else None
    if result is None:
     pump_gui(fig,.03);continue
    state,values=result
    # Display metadata belongs to this completed frame, even if a newer
    # request arrived while it was being captured.
    if controller is not None:
     if receiver:controller.settings=dict(state)
     else:controller.source=state['source']
     a.rate=controller.rate
    next_capture=time.monotonic()+a.interval
   else:
    if controller is not None:controller.apply_pending();a.rate=controller.rate
    values=cached if cached is not None else (acquire_iq(a.device,a.samples,a.timeout) if receiver and controller.mode=='iq' else (acquire_audio(a.device,a.samples,a.timeout) if receiver and controller.mode in ('usb','lsb') else acquire(a.device,a.samples,a.timeout)))
   if switching:
    pending=bool(controller.pending)
    plot.set_status('Change queued; current frame keeps previous settings.' if pending else SOURCE_LABELS[controller.source]+(' | 8 ksample/s I/Q' if receiver and controller.mode=='iq' else (' | 8 ksample/s '+controller.mode.upper()+' audio' if receiver and controller.mode in ('usb','lsb') else ' | %.0f MS/s'%(a.rate/1e6))))
   frames+=1;render(values)
   if a.save:fig.savefig(a.save,dpi=150);print('Saved '+a.save);break
   if a.once or cached is not None:plt.ioff();plt.show();break
   pump_gui(fig,.03)
 except KeyboardInterrupt:pass
 finally:
  if worker is not None:worker.close()
  plt.close(fig)

if __name__=='__main__':
 try:main()
 except (RuntimeError,IOError,ImportError,ValueError) as e:
  print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
