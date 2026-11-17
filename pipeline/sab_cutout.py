"""Remove one time range from a delivered final without re-rendering the episode.
usage: sab_cutout.py <in.mp4> <out.mp4> <t1> <t2>   (removes [t1, t2) in output seconds)
Video: stream-copies up to the last keyframe before t1 and from the first keyframe after t2, re-encoding only the
short pieces in between. Audio: cut sample-accurately with a 20 ms crossfade, re-encoded to AAC 192k."""
import sys, os, json, subprocess, tempfile, wave, numpy as np
src,dst,t1,t2=sys.argv[1],sys.argv[2],float(sys.argv[3]),float(sys.argv[4]); T=tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(dst)))
kf=[float(l.split(',')[0]) for l in subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','packet=pts_time,flags','-of','csv=p=0',src]).decode().split() if ',K' in l and l.split(',')[0] not in ('','N/A')]
dur=float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=duration','-of','csv=p=0',src]))
snap=lambda t: min(kf,key=lambda k:abs(k-t)) if min(abs(k-t) for k in kf)<2.1/24 else t
t1,t2=snap(t1),snap(t2)   # cuts usually land on segment starts, which are keyframes: then nothing is re-encoded
ka=max(k for k in kf if k<=t1+1e-3); kb=min([k for k in kf if k>=t2-1e-3]+[dur])
enc=['-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r','24']
def run(a): subprocess.run(['ffmpeg','-nostdin','-v','error']+a,check=True)
parts=[]
run(['-i',src,'-map','0:v','-frames:v',str(int(round(ka*24))),'-c','copy','-y',T+'/a.mp4']); parts.append(T+'/a.mp4')   # exact frame count (a -t copy can overrun a few frames)
if t1>ka+1e-3: run(['-ss',str(ka),'-i',src,'-map','0:v','-t',str(t1-ka)]+enc+['-y',T+'/b.mp4']); parts.append(T+'/b.mp4')
if kb>t2+1e-3: run(['-ss',str(t2),'-i',src,'-map','0:v','-t',str(kb-t2)]+enc+['-y',T+'/c.mp4']); parts.append(T+'/c.mp4')
if kb<dur-1e-3: run(['-ss',str(kb),'-i',src,'-map','0:v','-c','copy','-y',T+'/d.mp4']); parts.append(T+'/d.mp4')
ts=[]
for p in parts: run(['-i',p,'-c','copy','-bsf:v','h264_mp4toannexb','-f','mpegts','-y',p+'.ts']); ts.append(p+'.ts')
run(['-i','concat:'+'|'.join(ts),'-c','copy','-y',T+'/v.mp4'])   # MPEG-TS joins copied H.264 pieces with clean timestamps
vnew=float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=duration','-of','csv=p=0',T+'/v.mp4']))
t2=t1+(dur-vnew)   # cut the audio by exactly what the video lost (frame rounding at the joins), so sync holds after the cut
run(['-i',src,'-vn','-ac','2','-ar','48000','-y',T+'/a.wav'])
w=wave.open(T+'/a.wav'); x=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32).reshape(-1,2); SR=48000
i1,i2=int(round(t1*SR)),int(round(t2*SR)); f=int(0.02*SR); r=np.linspace(0,1,f)[:,None]
y=np.concatenate([x[:i1-f],x[i1-f:i1]*(1-r)+x[i2:i2+f]*r,x[i2+f:]])
o=wave.open(T+'/b.wav','wb'); o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR); o.writeframes(np.clip(y,-32768,32767).astype(np.int16).tobytes()); o.close()
run(['-i',T+'/v.mp4','-i',T+'/b.wav','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart','-y',dst])
for p in os.listdir(T): os.remove(os.path.join(T,p))
os.rmdir(T); print('cut',t1,t2,subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_type,duration','-of','csv=p=0',dst]).decode().split())
