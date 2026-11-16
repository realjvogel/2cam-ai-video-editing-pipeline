"""SAB RENDER: renders every EDL segment to video-only files (resumable), then assembles.
usage: sab_render.py <slug> segments <budget> | sab_render.py <slug> assemble"""
import os, sys, json, time, subprocess, numpy as np, wave
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from sab_cams import Cams
slug,mode=sys.argv[1],sys.argv[2]; BUD=float(sys.argv[3]) if len(sys.argv)>3 else 150; T0=time.time()
SSD=os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')); ROOT=SSD+'/SAB-production'; A=ROOT+'/assets/look-c'
W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug); E=f'{ROOT}/episodes/{slug}'; os.makedirs(W+'/vo',exist_ok=True)
edl=json.load(open(W+'/edl.json')); prep=json.load(open(W+'/prep.json')); OFF=prep['offset']; FLIP='hflip,vflip,' if prep['flip_front'] else ''
K=edl.get('out_k',1); OWs,OHs=1920*K,1080*K; front,top=prep['front'],prep['top']; C=Cams(W,edl); faces=edl['faces']
ENC=['-an','-c:v','libx264','-preset','veryfast','-crf','18' if edl.get('out_k',1)==1 else '20','-pix_fmt','yuv420p','-r','24']
def sh(cmd):
    try: return subprocess.run(cmd,capture_output=True,text=True,timeout=max(5,BUD-(time.time()-T0)+20))
    except subprocess.TimeoutExpired: return subprocess.CompletedProcess(cmd,1,'','timeout')
def crop(z,cx,cy):
    cw,ch=3840/z,2160/z; x=min(max(cx*3840-cw/2,0),3840-cw); y=min(max(cy*2160-ch/2,0),2160-ch)
    return f"crop={int(cw)//2*2}:{int(ch)//2*2}:{int(x)}:{int(y)},scale={OWs}:{OHs}"
def review_crop(t):
    l,r=C._at(C.L,t),C._at(C.R,t); x0,y0,x1,y1=min(l[0],r[0]),min(l[1],r[1]),max(l[2],r[2]),max(l[3],r[3]); m=0.03
    cw=max((x1-x0+2*m)/0.72,y1-y0+2*m); cw=min(cw,1.0); x=max(0,min(x0-m,1-cw)); y=max(0,min((y0+y1)/2-cw/2,1-cw))
    return crop(1/cw,x+cw/2,y+cw/2)
def pip_crop():   # landscape crop around both faces in the 4K front frame (after flip)
    k,a=faces['kid'],faces['adult']; x0=min(k[0],a[0])-0.21; x1=max(k[0],a[0])+0.19; w=min(1.0,x1-x0); h=min(1.0,w*3840*325/520/2160)   # pixel aspect must match the 520x325 card
    cy=(k[1]+a[1])/2+0.05; y0=max(0,min(cy-h/2,1-h)); x0=max(0,min(x0,1-w))
    return f"crop={int(w*3840)//2*2}:{int(h*2160)//2*2}:{int(x0*3840)}:{int(y0*2160)},scale={520*K}:{325*K}"
def render(s):
    out=f"{W}/vo/{s['name']}.mp4"
    if os.path.exists(out): return True
    a,b,sp,role,cam=s['a'],s['b'],s.get('speed',1),s['role'],s['cam']; d=b-a; tmp=out+'.tmp.mp4'
    if role=='intro': return False     # made by sab_intro.py
    if role=='outro_video':
        r=sh(['ffmpeg','-nostdin','-v','error','-ss','1.0','-i',E+'/outro_anim_v.mp4','-vf',f'fps=24,setpts=PTS-STARTPTS,scale={OWs}:{OHs}:flags=lanczos']+ENC+['-y',tmp])
    elif cam=='front':
        r=sh(['ffmpeg','-nostdin','-v','error','-ss',str(a+OFF),'-t',str(d),'-i',front,'-vf',f"{FLIP}scale={OWs}:{OHs},setpts=(PTS-STARTPTS)/{sp},fps=24",'-t',f'{d/sp:.3f}']+ENC+['-y',tmp])
    elif cam=='top' and role=='montage':
        r=sh(['ffmpeg','-nostdin','-v','error','-ss',str(a),'-t',str(d),'-i',top,'-vf',f"{crop(*C.base((a+b)/2))},setpts=(PTS-STARTPTS)/{sp},fps=24",'-t',f'{d/sp:.3f}']+ENC+['-y',tmp])
    elif cam=='top':
        r=sh(['python3',os.path.dirname(os.path.abspath(__file__))+'/sab_camrender.py',W,W+'/edl.json',top,str(a),str(d),tmp])
    elif cam=='wipe':
        r=sh(['ffmpeg','-nostdin','-v','error','-ss',str(a+OFF),'-t',str(d),'-i',front,'-ss',str(s['top_a']),'-t',str(d),'-i',top,'-filter_complex',
          f"[0:v]{FLIP}scale={OWs}:{OHs},fps=24,setpts=PTS-STARTPTS[f];[1:v]{crop(*C.base(s['top_a']+d))},fps=24,setpts=PTS-STARTPTS[t];[f][t]xfade=transition=diagtl:duration={d-0.05:.2f}:offset=0[v]",'-map','[v]','-t',str(d)]+ENC+['-y',tmp])
    elif cam=='review':
        r=sh(['ffmpeg','-nostdin','-v','error','-ss',str(a),'-t',str(d),'-i',top,'-ss',str(a+OFF),'-t',str(d),'-i',front,'-i',A+'/pip3_shadow.png','-i',A+'/pip3_border.png','-i',A+'/pip3_mask.png','-filter_complex',
          f"[0:v]setpts=PTS-STARTPTS,fps=24,{review_crop((a+b)/2)}[b];[1:v]setpts=PTS-STARTPTS,fps=24,{FLIP}{pip_crop()},format=rgba[f];[4:v]format=gray,scale={520*K}:{325*K}[mk];[f][mk]alphamerge[fm];[2:v]scale={OWs}:{OHs}[sh];[3:v]scale={OWs}:{OHs}[bd];[b][sh]overlay=0:0[s];[s][fm]overlay={1380*K}:{712*K}[x];[x][bd]overlay=0:0,format=yuv420p[v]",'-map','[v]','-t',str(d)]+ENC+['-y',tmp])
    elif cam=='iris':
        r=sh(['python3',os.path.dirname(os.path.abspath(__file__))+'/sab_iris.py',slug,str(a)])
        return r.returncode==0 and os.path.exists(out)
    else: return False
    if r.returncode: print(s['name'],'ERR',r.stderr[-400:]); return False
    os.rename(tmp,out); print(s['name'],'ok',round(time.time()-T0)); return True
if mode=='segments':
    for s in edl['segments']:
        if time.time()-T0>BUD: break
        render(s)
    miss=[s['name'] for s in edl['segments'] if not os.path.exists(f"{W}/vo/{s['name']}.mp4")]; print('missing',miss)
elif mode=='assemble':
    SR=48000
    def rd(p): w=wave.open(p); return np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32).reshape(-1,2)/32768
    def vdur(f): return float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=duration','-of','csv=p=0',f]))
    S=edl['segments']; dlg=rd(W+'/dlg48.wav'); mus=rd(W+'/music48.wav')
    durs=[vdur(f"{W}/vo/{s['name']}.mp4") for s in S]; N=int(round(sum(durs)*SR)); out=np.zeros((N,2),np.float32)
    def place(buf,pos,gain=1.0,fin=0.01,fout=0.01):
        n=min(len(buf),N-pos); bb=buf[:n].copy()*gain; fi=int(fin*SR); fo=int(fout*SR)
        if fi: bb[:fi]*=np.linspace(0,1,fi)[:,None]
        if fo: bb[-fo:]*=np.linspace(1,0,fo)[:,None]
        out[pos:pos+n]+=bb
    t=0.0; marks={}
    for s,d in zip(S,durs):
        p=int(round(t*SR)); n=int(round(d*SR)); marks[s['name']]=(p,n)
        if s['role'] not in ('montage','outro_video','wipe'):
            st=int(round(s['a']*SR)); place(dlg[st:st+n],p,1.0,0.01,0.5 if s['role']=='iris' else 0.01)
        t+=d
    M=edl['music']
    if M.get('stinger'): place(mus[:int(3.5*SR)],0,0.28,0.02,1.2)
    mon=[s['name'] for s in S if s['role']=='montage']; m0=marks[mon[0]][0]; m1=marks[mon[-1]][0]+marks[mon[-1]][1]
    place(mus[int(M['montage_from']*SR):int(M['montage_from']*SR)+m1-m0],m0,0.5,0.3,1.2)
    e0=marks['iris'][0]; L=N-e0; place(mus[len(mus)-L:],e0,0.55,0.3,0.2)
    out=np.clip(out,-1,1); w=wave.open(W+'/mix.wav','wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out*32767).astype(np.int16).tobytes()); w.close()
    open(W+'/list.txt','w').write(''.join(f"file '{W}/vo/{s['name']}.mp4'\n" for s in S))
    bug_on=edl['title']['t_out_local']+0.3; bug_off=e0/SR
    json.dump({'bug_on':bug_on,'bug_off':bug_off,'dur':sum(durs)},open(W+'/finalize.json','w'))
    print('mixed + joined', round(sum(durs),2),'s -> run finalize')
elif mode=='finalize':   # bug overlay on groups of whole segments (no seeking -> no duplicated frames), then join + mux the loudnormed mix
    F=json.load(open(W+'/finalize.json')); os.makedirs(W+'/parts',exist_ok=True)
    def vdur(f): return float(subprocess.check_output(['ffprobe','-v','error','-select_streams','v','-show_entries','stream=duration','-of','csv=p=0',f]))
    names=[l.split("'")[1] for l in open(W+'/list.txt') if l.strip()]
    if not os.path.exists(W+'/groups.json'):
        G=[];cur=[];acc=0;t=0;starts=[]
        for n in names:
            d=vdur(n)
            if cur and acc+d>(60 if K==2 else 150): G.append((starts[0],cur)); cur=[];acc=0;starts=[]
            if not cur: starts=[t]
            cur.append(n); acc+=d; t+=d
        G.append((starts[0],cur)); json.dump(G,open(W+'/groups.json','w'))
    G=json.load(open(W+'/groups.json')); done=True
    for k,(t0,grp) in enumerate(G):
        o=f"{W}/parts/p{k:02d}.mp4"
        if os.path.exists(o): continue
        if time.time()-T0>BUD-60: done=False; break
        open(W+f'/g{k}.txt','w').write(''.join(f"file '{n}'\n" for n in grp))
        on,off=F['bug_on']-t0,F['bug_off']-t0
        r=subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','0','-i',W+f'/g{k}.txt','-i',A+'/wordmark_bug_corner.png','-filter_complex',
            f"[1:v]scale=iw*{K}:ih*{K}[bug];[0:v][bug]overlay=0:0:enable='between(t,{on},{off})',format=yuv420p[v]",'-map','[v]','-c:v','libx264','-preset','veryfast','-crf','18' if K==1 else '20','-r','24','-y',o+'.tmp.mp4'],capture_output=True,text=True)
        if r.returncode: print('part',k,'ERR',r.stderr[-300:]); done=False; break
        os.rename(o+'.tmp.mp4',o); print('part',k,'ok',round(time.time()-T0),flush=True)
    if done:
        open(W+'/plist.txt','w').write(''.join(f"file '{W}/parts/p{i:02d}.mp4'\n" for i in range(len(G))))
        if not os.path.exists(W+'/mix_norm.m4a'):
            subprocess.run(['ffmpeg','-nostdin','-v','error','-i',W+'/mix.wav','-af','highpass=f=70,loudnorm=I=-14:TP=-1.5:LRA=11','-c:a','aac','-b:a','192k','-ar','48000','-y',W+'/mix_norm.m4a'])
        r=sh(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','0','-i',W+'/plist.txt','-i',W+'/mix_norm.m4a','-map','0:v','-map','1:a','-c','copy','-movflags','+faststart','-y',W+'/final.mp4'])
        print('final', r.returncode, r.stderr[-300:])
