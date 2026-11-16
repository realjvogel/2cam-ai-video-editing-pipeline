"""SAB pipeline — PREP. Resumable; every step skips if its output exists.
usage: python3 sab_prep.py <slug> <front.mov> <top.mov> [--flip-front] [budget_s]
Work dir (fast scratch): ~/sab/eps/<slug>/ ; episode state on SSD: SAB-production/episodes/<slug>/"""
import os, sys, json, time, subprocess, glob
import numpy as np, wave, cv2
SSD=os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')); ROOT=SSD+'/SAB-production'
slug,front,top=sys.argv[1],sys.argv[2],sys.argv[3]; FLIP='--flip-front' in sys.argv
BUD=float([a for a in sys.argv[4:] if a[0].isdigit()][0]) if any(a[0].isdigit() for a in sys.argv[4:]) else 160; T0=time.time()
W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug); E=f'{ROOT}/episodes/{slug}'; os.makedirs(W+'/top',exist_ok=True); os.makedirs(W+'/front',exist_ok=True); os.makedirs(E,exist_ok=True)
P=lambda f: f if f.startswith('/') else SSD+'/Projects/'+f
front,top=P(front),P(top)
def left(): return BUD-(time.time()-T0)
def sh(cmd,timeout=None):
    try: return subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired: return subprocess.CompletedProcess(cmd,1,'','timeout')
st=json.load(open(E+'/prep.json')) if os.path.exists(E+'/prep.json') else {}
def save(): json.dump(st,open(E+'/prep.json','w'),indent=1)
st.update(slug=slug,front=front,top=top,flip_front=FLIP)
def dur(f): return float(sh(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',f]).stdout)
st.setdefault('dur_front',dur(front)); st.setdefault('dur_top',dur(top)); save()
# 1) audio: 8k mono for sync, 48k stereo dialogue (top), 16k mono for transcription (to SSD)
jobs=[(top,W+'/top8k.wav',['-ac','1','-ar','8000']),(front,W+'/front8k.wav',['-ac','1','-ar','8000']),(top,W+'/dlg48.wav',['-ac','2','-ar','48000']),(top,E+'/top16k.wav',['-ac','1','-ar','16000','-c:a','pcm_s16le'])]
for src,dst,args in jobs:
    if os.path.exists(dst) or left()<40: continue
    r=sh(['ffmpeg','-nostdin','-v','error','-i',src,'-vn']+args+['-y',dst+'.tmp.wav'],timeout=max(10,left()-5))
    if r.returncode==0: os.rename(dst+'.tmp.wav',dst); print('audio',os.path.basename(dst))
# 2) sync offset (front_time = top_time + offset) via raw xcorr at 3 points
if 'offset' not in st and os.path.exists(W+'/top8k.wav') and os.path.exists(W+'/front8k.wav'):
    from scipy.signal import fftconvolve
    rd=lambda p:(lambda w:np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32))(wave.open(p))
    a=rd(W+'/top8k.wav'); b=rd(W+'/front8k.wav'); L=min(len(a),len(b))/8000; offs=[]
    for t in (L*0.2,L*0.5,L*0.8):
        t=int(t); q=b[t*8000:(t+20)*8000]; seg=a[max(0,(t-30))*8000:(t+50)*8000]
        c=fftconvolve(seg,q[::-1],'valid'); i=int(c.argmax()); offs.append(t-(max(0,t-30)+i/8000))
    st['offset']=float(np.median(offs)); st['offset_spread']=float(np.ptp(offs)); save(); print('offset',offs)
# 3) 1 fps keyframe frames (resumable)
for name,src,vf in (('top',top,''),('front',front,',hflip,vflip' if FLIP else '')):
    d=W+'/'+name; n=len(glob.glob(d+'/*.jpg')); total=int(st['dur_top' if name=='top' else 'dur_front'])
    if n>=total-1 or left()<30: continue
    n=max(0,n-2); [os.remove(f) for f in sorted(glob.glob(d+'/*.jpg'))[n:]]
    sh(['timeout',str(int(left()-10)),'ffmpeg','-nostdin','-v','error','-ss',str(n),'-skip_frame','nokey','-i',src,'-vf',f'fps=1,scale=320:-2{vf}','-q:v','5','-start_number',str(n+1),'-y',d+'/%04d.jpg'])
    print(name,'frames',len(glob.glob(d+'/*.jpg')),'/',total)
# 4) paper boxes + pen activity per second (needs all top frames)
fs=sorted(glob.glob(W+'/top/*.jpg'))
if 'papers' not in st and len(fs)>=int(st['dur_top'])-1:
    out=[]; act=[]; prev=None
    for i,f in enumerate(fs):
        im=cv2.imread(f); h,w=im.shape[:2]; hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
        m=((hsv[...,1]<45)&(hsv[...,2]>160)).astype(np.uint8)*255; m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        cs,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE); cs=sorted([c for c in cs if 0.04*w*h<cv2.contourArea(c)<0.3*w*h],key=cv2.contourArea,reverse=True)[:2]
        g=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY).astype(np.float32)
        if len(cs)==2:
            r=sorted([cv2.boundingRect(c) for c in cs]); out.append([i]+[v for x,y,ww,hh in r for v in (x/w,y/h,(x+ww)/w,(y+hh)/h)])
        if prev is not None:
            b=out[-1][1:] if out else [0.2,0.25,0.5,0.9,0.5,0.25,0.8,0.9]; x0,y0,x1,y1=int(min(b[0],b[4])*w),int(min(b[1],b[5])*h),int(max(b[2],b[6])*w),int(max(b[3],b[7])*h)
            act.append([i,float((np.abs(g-prev)[y0:y1,x0:x1]>25).mean())])
        prev=g
    json.dump(out,open(E+'/papers.json','w')); json.dump(act,open(E+'/activity.json','w')); st['papers']=len(out); save()
    print('papers detected',len(out),'of',len(fs))
done=all(os.path.exists(p) for p in (W+'/dlg48.wav',E+'/top16k.wav')) and 'offset' in st and 'papers' in st
print('PREP DONE' if done else 'PREP PARTIAL', round(time.time()-T0),'s')
