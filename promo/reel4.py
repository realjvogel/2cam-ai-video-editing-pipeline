import subprocess, os, sys
SSD=os.path.expanduser('~/sab-data')
FIN=f'{SSD}/SAB - auto edits/How To Draw A Popsicle & Cone With Kid B - v2.mp4'
FRONT=f'{SSD}/Projects/IMG_0265.mov'; TOP=f'{SSD}/Projects/IMG_0013.mov'
RAG=f'{SSD}/Projects/Cartoon_Band_Rag.m4a'
T=0.35
# (kind, src/a, dur, [(overlay, in, out)])
S=[('card','ov/c_open3.png',3.0,[]),
   ('raw',17.0,5.4,[('k_raw',T,2.9)]),
   ('fin',2.0,13.2,[('k_punch',T,2.5),('k_title',6.0,8.3)]),
   ('zoom',58.0,8.0,[('k_zoom',T,2.6)]),
   ('fin',112.0,4.6,[('k_cut',T,2.55)]),
   ('fin',797.2,4.6,[('k_montage',T,2.6)]),
   ('fin',858.0,4.6,[('k_review',T,2.6)]),
   ('fin',907.2,5.6,[('k_outro',T,2.2)]),
   ('card','ov/c_end2.png',4.0,[])]
def run(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode: print(r.returncode,r.stderr[-1200:]); sys.exit(1)
os.makedirs('clips4',exist_ok=True); os.makedirs('parts4',exist_ok=True)
ENC=['-c:v','libx264','-preset','veryfast','-crf','17','-pix_fmt','yuv420p','-r','24','-c:a','pcm_s16le','-ar','48000','-ac','2']
def sm(t0,d): return f"(st(1,clip((in/24-{t0})/{d},0,1))*0+ld(1)*ld(1)*(3-2*ld(1)))"
stage=sys.argv[1]; only=[int(x) for x in sys.argv[2:]]
if stage=='a':
  for k,(kind,a,d,ovs) in enumerate(S):
    if only and k not in only: continue
    f=[]
    if kind=='raw':
        inp=['-loop','1','-framerate','24','-t',str(d),'-i','ov/rawbg3.png','-ss',str(a),'-t',str(d),'-i',FRONT,'-ss',str(a),'-t',str(d),'-i',TOP]
        f.append('[1:v]hflip,vflip,scale=880:495,setpts=PTS-STARTPTS[f];[2:v]scale=880:495,setpts=PTS-STARTPTS[t];[0:v][f]overlay=60:292:shortest=1[b];[b][t]overlay=980:292:shortest=1[base]')
        f.append('[2:a]asetpts=PTS-STARTPTS[ca]')
    elif kind=='zoom':
        inp=['-ss',str(a),'-t',str(d),'-i',TOP]
        # paper centers (norm): L (0.30,0.496)  R (0.726,0.543); zoom 1.8
        E1=sm(2.8,1.2); E2=sm(5.0,1.3)
        Z=f"(1+0.8*{E1})"
        CX=f"(0.5-0.2*{E1}+0.426*{E2})"; CY=f"(0.5-0.004*{E1}+0.047*{E2})"
        zx=f"max(0,min(iw-iw/zoom,{CX}*iw-iw/zoom/2))"; zy=f"max(0,min(ih-ih/zoom,{CY}*ih-ih/zoom/2))"
        f.append(f"[0:v]setpts=PTS-STARTPTS,zoompan=z='{Z}':x='{zx}':y='{zy}':d=1:s=1920x1080:fps=24[base]")
        f.append('[0:a]asetpts=PTS-STARTPTS[ca]')
    elif kind=='fin':
        inp=['-ss',str(a),'-t',str(d),'-i',FIN]; f.append('[0:v]setpts=PTS-STARTPTS[base]'); f.append('[0:a]asetpts=PTS-STARTPTS[ca]')
    else:
        inp=['-loop','1','-framerate','24','-t',str(d),'-i',a,'-f','lavfi','-t',str(d),'-i','anullsrc=r=48000:cl=stereo']
        f.append('[0:v]format=yuv420p[base]'); f.append('[1:a]anull[ca]')
    n0=inp.count('-i'); last='base'
    for i,(png,ti,to) in enumerate(ovs):
        inp+=['-loop','1','-framerate','24','-t',str(d),'-i',f'ov/{png}.png']; ix=n0+i
        f.append(f'[{ix}:v]format=rgba,fade=in:st={ti}:d=0.2:alpha=1,fade=out:st={to}:d=0.25:alpha=1[l{i}];[{last}][l{i}]overlay=0:0:shortest=1[o{i}]'); last=f'o{i}'
    f.append(f'[{last}]fps=24,setsar=1,format=yuv420p,trim=duration={d}[v]')
    f.append(f'[ca]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={d}[a]')
    run(['ffmpeg','-y','-v','error']+inp+['-filter_complex',';'.join(f),'-map','[v]','-map','[a]']+ENC+['-t',str(d),f'clips4/{k}.tmp.mov'])
    os.replace(f'clips4/{k}.tmp.mov',f'clips4/{k}.mov'); print('clip',k,flush=True)
  sys.exit(0)
# stage b
trans=['fade']+['slideleft']*6+['fade']
parts=[]; N=len(S)
for k,(kind,a,d,ovs) in enumerate(S):
    st=T if k>0 else 0; en=d-T if k<N-1 else d
    vf='fade=t=in:d=0.25,' if k==0 else ''
    p=f'parts4/b{k}.mov'
    run(['ffmpeg','-y','-v','error','-ss',str(st),'-t',f'{en-st:.3f}','-i',f'clips4/{k}.mov','-vf',vf+'setpts=PTS-STARTPTS','-af','asetpts=PTS-STARTPTS']+ENC+[p]); parts.append(p)
    if k<N-1:
        p=f'parts4/t{k}.mov'
        fc=(f'[0:v]settb=AVTB,setpts=PTS-STARTPTS[x];[1:v]settb=AVTB,setpts=PTS-STARTPTS[y];[x][y]xfade=transition={trans[k]}:duration={T}:offset=0[v];'
            f'[0:a]afade=t=out:d={T}[p];[1:a]afade=t=in:d={T}[q];[p][q]amix=inputs=2:normalize=0[a]')
        run(['ffmpeg','-y','-v','error','-ss',f'{d-T:.3f}','-t',str(T),'-i',f'clips4/{k}.mov','-t',str(T),'-i',f'clips4/{k+1}.mov','-filter_complex',fc,'-map','[v]','-map','[a]']+ENC+['-t',str(T),p]); parts.append(p)
open('parts4/list.txt','w').write(''.join(f"file '{os.path.basename(p)}'\n" for p in parts))
run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i','parts4/list.txt','-c','copy','parts4/joined.mov'])
total=float(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0','parts4/joined.mov'],capture_output=True,text=True).stdout)
body=total-6.0
fc=(f'[1:a]atrim=0:{body+1.0},asetpts=PTS-STARTPTS,afade=t=in:d=0.3[mb];[2:a]atrim=0:7.0,asetpts=PTS-STARTPTS[me];[mb][me]acrossfade=d=1.0,atrim=0:{total},volume=0.9[mus];'
    f'[0:a]volume=0.22[dia];[mus][dia]amix=inputs=2:normalize=0:duration=first,afade=t=out:st={total-0.6}:d=0.6,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[aout]')
run(['ffmpeg','-y','-v','error','-i','parts4/joined.mov','-i',RAG,'-ss','172.3','-i',RAG,'-filter_complex',fc,'-map','0:v','-map','[aout]','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart','-t',f'{total:.3f}','reel4.tmp.mp4'])
os.replace('reel4.tmp.mp4','reel4.mp4'); print('done',total)
