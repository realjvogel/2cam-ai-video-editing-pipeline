"""Patch a delivered episode: swap in a re-rendered first part (intro + wipe + lesson start) and the wipe's new dialogue, keep the rest untouched.
usage: sab_patch.py <slug> <old_final.mp4> <new_final.mp4>   (needs W/vo for every segment in groups.json[0])"""
import json, os, sys, subprocess, wave, numpy as np
slug,old,new=sys.argv[1:4]; W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug); A=os.path.join(os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')),'SAB-production','assets','look-c')
edl=json.load(open(W+'/edl.json')); K=edl.get('out_k',1); F=json.load(open(W+'/finalize.json')); G=json.load(open(W+'/groups.json'))
def vdur(f): return float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=duration','-of','csv=p=0',f]))
grp=[os.path.join(W,'vo',os.path.basename(n)) for n in G[0][1]]; CUT=G[0][2] if len(G[0])>2 else None
T1=CUT if CUT else sum(vdur(n) for n in grp)   # CUT: old finals made in fixed-length parts (keyframe at CUT)
open(W+'/g0.txt','w').write(''.join(f"file '{n}'\n" for n in grp))
p0=W+'/p00_new.mp4'
if not os.path.exists(p0):
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','0','-i',W+'/g0.txt','-i',A+'/wordmark_bug_corner.png','-filter_complex',
        f"[1:v]scale=iw*{K}:ih*{K}[bug];[0:v][bug]overlay=0:0:enable='between(t,{F['bug_on']},{F['bug_off']})',format=yuv420p[v]",'-map','[v]']+(['-t',str(CUT)] if CUT else [])+['-c:v','libx264','-preset','veryfast','-crf','18' if K==1 else '20','-r','24','-y',p0+'.tmp.mp4'],check=True)
    os.rename(p0+'.tmp.mp4',p0)
print('T1',round(T1,3),'p00',round(vdur(p0),3))
tail=W+'/tail.mp4'
if not os.path.exists(tail): subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(T1),'-i',old,'-map','0:v','-c','copy','-y',tail],check=True)
# audio: old mix with the wipe region replaced by the lesson's lead-in dialogue
subprocess.run(['ffmpeg','-nostdin','-v','error','-i',old,'-vn','-ac','2','-ar','48000','-y',W+'/old_audio.wav'],check=True)
def rd(p): w=wave.open(p); return np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32).reshape(-1,2)
au=rd(W+'/old_audio.wav'); dlg=rd(W+'/dlg48.wav'); SR=48000
S=edl['segments']; intro_d=vdur(W+'/vo/intro.mp4'); wseg=[s for s in S if s['role']=='wipe'][0]; wd=vdur(W+'/vo/wipe.mp4')
d0=[s for s in S if s['role']=='draw'][0]
ref_o=au[int((intro_d+wd)*SR):int((intro_d+wd+20)*SR)]; ref_d=dlg[int(d0['a']*SR):int((d0['a']+20)*SR)]
g=np.sqrt((ref_o**2).mean())/max(1,np.sqrt((ref_d**2).mean())); print('gain',round(float(g),3))
a0=int(intro_d*SR); n=int(wd*SR); seg=dlg[int(wseg['a']*SR):int(wseg['a']*SR)+n]*g          # intro continues under the wipe...
fo=int(0.5*SR); seg[-fo:]*=np.linspace(1,0,fo)[:,None]; au[a0:a0+n]=seg
fi=int(0.25*SR); au[a0+n:a0+n+fi]*=np.linspace(0,1,fi)[:,None]                                     # ...and the lesson fades in
w=wave.open(W+'/patched.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.clip(au,-32768,32767).astype(np.int16).tobytes()); w.close()
open(W+'/patch_list.txt','w').write(f"file '{p0}'\nfile '{tail}'\n")
subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','0','-i',W+'/patch_list.txt','-i',W+'/patched.wav','-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart','-y',new],check=True)
print('patched', subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_type,duration','-of','csv=p=0',new]).decode().split())
