"""Re-encode only some finalize groups of a delivered episode and splice them into the old final (video only;
the audio is kept, so segment lengths must be unchanged, e.g. after a camera-only change).
usage: sab_regroup.py <slug> <old_final.mp4> <new_final.mp4> <k,k,...> [budget]
Needs W/vo for every segment in the listed groups (render them with `sab_render.py <slug> only ...`).
Each finalize group was encoded on its own, so every group starts on a keyframe and the copies are exact."""
import json, os, sys, time, subprocess
slug,old,new,ks=sys.argv[1:5]; BUD=float(sys.argv[5]) if len(sys.argv)>5 else 160; T0=time.time()
W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug); A=os.path.join(os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')),'SAB-production','assets','look-c')
edl=json.load(open(W+'/edl.json')); K=edl.get('out_k',1); F=json.load(open(W+'/finalize.json')); G=json.load(open(W+'/groups.json'))
ks=[int(k) for k in ks.split(',')]; os.makedirs(W+'/regroup',exist_ok=True)
def vdur(f): return float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=duration','-of','csv=p=0',f]))
total=vdur(old); parts=[]
KF=[float(l.split(',')[0]) for l in subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','packet=pts_time,flags','-of','csv=p=0',old]).decode().split() if ',K' in l and l.split(',')[0] not in ('','N/A')]
kf=lambda t: min(KF,key=lambda k:abs(k-t))   # each group starts on a keyframe; seek just past it so the copy starts exactly there
for i,(t0,grp) in enumerate(G):
    t1=G[i+1][0] if i+1<len(G) else total; o=f"{W}/regroup/p{i:02d}.mp4"
    if not os.path.exists(o):
        if time.time()-T0>BUD-50: print('budget; rerun'); sys.exit(0)
        if i in ks:
            names=[os.path.join(W,'vo',os.path.basename(n)) for n in grp]; open(W+f'/regroup/g{i}.txt','w').write(''.join(f"file '{n}'\n" for n in names))
            subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','0','-i',W+f'/regroup/g{i}.txt','-i',A+'/wordmark_bug_corner.png','-filter_complex',
                f"[1:v]scale=iw*{K}:ih*{K}[bug];[0:v][bug]overlay=0:0:enable='between(t,{F['bug_on']-t0},{F['bug_off']-t0})',format=yuv420p[v]",'-map','[v]',
                '-c:v','libx264','-preset','veryfast','-crf','18' if K==1 else '20','-r','24','-y',o+'.tmp.mp4'],check=True)
        else:
            subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(kf(t0)+0.01),'-i',old,'-map','0:v','-frames:v',str(int(round((t1-t0)*24))),'-c','copy','-avoid_negative_ts','make_zero','-y',o+'.tmp.mp4'],check=True)   # exact frame count
        os.rename(o+'.tmp.mp4',o); print('part',i,'new' if i in ks else 'copied',round(vdur(o),3),'expected',round(t1-t0,3),flush=True)
    parts.append(o)
ts=[]
for p in parts:   # MPEG-TS joins copied H.264 pieces with clean timestamps
    if not os.path.exists(p+'.ts'): subprocess.run(['ffmpeg','-nostdin','-v','error','-i',p,'-c','copy','-bsf:v','h264_mp4toannexb','-f','mpegts','-y',p+'.ts'],check=True)
    ts.append(p+'.ts')
subprocess.run(['ffmpeg','-nostdin','-v','error','-i','concat:'+'|'.join(ts),'-i',old,'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart','-y',new],check=True)
print('regrouped', subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_type,duration','-of','csv=p=0',new]).decode().split())
