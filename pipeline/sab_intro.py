"""Intro: front cam with face-safe punch-ins, optional cut ranges (segment `keep`), softened background, animated Look C title behind the people.
Needs: W/edl.json (intro segment, title timing, punchins), E/intro_alpha.mp4 (person matte of the 1080 proxy), E/subject-aligned.png"""
import cv2, numpy as np, subprocess, json, os, sys
from PIL import Image
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from sab_faces import face_safe
slug=sys.argv[1]; PK=int(sys.argv[2]) if len(sys.argv)>2 else 0; PN=int(sys.argv[3]) if len(sys.argv)>3 else 1; SSD=os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')); R=SSD+'/SAB-production'; E=f'{R}/episodes/{slug}'; W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug)
prep=json.load(open(W+'/prep.json')); edl=json.load(open(W+'/edl.json')); seg=[s for s in edl['segments'] if s['role']=='intro'][0]
a,b=seg['a'],seg['b']; KEEP=seg.get('keep') or [[a,b]]; DUR=sum(y-x for x,y in KEEP)
def l2r(t):   # local intro seconds -> raw front-cam (top-clock) seconds, skipping cut ranges
    for x,y in KEEP:
        if t<=y-x: return x+t
        t-=y-x
    return KEEP[-1][1]
RF=lambda n: int(round((l2r(n/24)-a)*24))   # raw frame index (from the intro start) for output frame n
K=edl.get('out_k',1); SW,SH,OW,OH,FPS=3840,2160,1920*K,1080*K,24; ti=edl['title']
shots=edl['intro_shots']   # [t0,t1,[z,cx,cy],[z,cx,cy],ease] in local intro seconds
def ease(p,k): p=min(max(p,0),1); return p*p*(3-2*p) if k=='smooth' else (1-(1-p)**3 if k=='out' else p)
def cam(t):
    for s0 in shots:
        t0,t1,v0,v1,k=s0
        if t<t1 or s0 is shots[-1]: e=ease((t-t0)/max(t1-t0,1e-3),k); return [v0[i]+(v1[i]-v0[i])*e for i in range(3)]
def prep_img(path,width):
    im=Image.open(path).convert('RGBA'); im=im.resize((width,int(im.height*width/im.width)),Image.LANCZOS); x=np.asarray(im).astype(np.float32); return x[...,:3][...,::-1].copy(),x[...,3:]/255
HDR=prep_img(R+'/assets/look-c/'+edl.get('header','video-how-to-draw-a.png'),779*K); SUB=prep_img(E+'/subject-aligned.png',779*K)
def paste(bg,img,x,y,al):
    c,aa=img; h,w=aa.shape[:2]; x0,y0,x1,y1=max(0,x),max(0,y),min(OW,x+w),min(OH,y+h)
    if x1<=x0 or y1<=y0: return bg
    m=aa[y0-y:y1-y,x0-x:x1-x]*al; bg[y0:y1,x0:x1]=bg[y0:y1,x0:x1]*(1-m)+c[y0-y:y1-y,x0-x:x1-x]*m; return bg
def back(p): p=min(max(p,0),1); c=1.70158; return 1+(c+1)*(p-1)**3+c*(p-1)**2
vf=('hflip,vflip,' if prep['flip_front'] else '')+'fps=24'
def title_place():
    """Find the largest title scale + position (1080 units) where header+subject never cover a head during the title window."""
    fp=W+'/title_place.json'
    if os.path.exists(fp): return json.load(open(fp))
    TH_,TO_=edl['title']['t_header_local'],edl['title']['t_out_local']
    p=subprocess.Popen(['ffmpeg','-v','error','-i',E+'/intro_alpha.mp4','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE); M=np.zeros((1080,1920),bool); k=0
    while True:
        b=p.stdout.read(1920*1080)
        if len(b)<1920*1080: break
        if RF(TH_*24)-6<=k<=RF(TO_*24)+10 and k%3==0: M|=np.frombuffer(b,np.uint8).reshape(1080,1920)>110
        k+=1
    fc=edl['faces']; kx,ky=fc['kid']; ax,ay=fc['adult']; split=int((kx+ax)/2*1920)
    head=np.zeros_like(M); FL,FR=(fc['kid'],fc['adult']) if kx<ax else (fc['adult'],fc['kid'])
    head[:int((FL[1]+0.17)*1080),:split]=True; head[:int((FR[1]+0.17)*1080),split:]=True; head&=M
    for fx,fy in (fc['kid'],fc['adult']): cv2.ellipse(head,(int(fx*1920),int(fy*1080)),(int(0.075*1920),int(0.15*1080)),0,0,360,1,-1) if False else None
    hm=head.astype(np.uint8); [cv2.ellipse(hm,(int(fx*1920),int(fy*1080)),(140,170),0,0,360,1,-1) for fx,fy in (fc['kid'],fc['adult'])]
    hm=cv2.dilate(hm,np.ones((41,41),np.uint8)); D=4; hs=cv2.resize(hm.astype(np.float32),(1920//D,1080//D),interpolation=cv2.INTER_AREA)
    mm=cv2.dilate((M|hm.astype(bool)).astype(np.uint8),np.ones((25,25),np.uint8)); ms=cv2.resize(mm.astype(np.float32),(1920//D,1080//D),interpolation=cv2.INTER_AREA)   # header sits behind people, so it must clear every person
    ha=np.asarray(Image.open(R+'/assets/look-c/'+edl.get('header','video-how-to-draw-a.png')).convert('RGBA'))[...,3]; sa=np.asarray(Image.open(E+'/subject-aligned.png').convert('RGBA'))[...,3]
    def search(front):
        for sc in np.arange(1.0,0.44,-0.05):
            w=int(779*sc/D); h1=int(ha.shape[0]*w/ha.shape[1]); h2=int(sa.shape[0]*w/sa.shape[1]); off=int(184*sc/D)
            TH1=np.zeros((off+h2,w),np.float32); TH1[:h1]=cv2.resize(ha,(w,h1))/255.
            TS1=np.zeros((off+h2,w),np.float32); TS1[off:off+h2]=cv2.resize(sa,(w,h2))/255.
            if TH1.shape[0]>hs.shape[0]-8 or TH1.shape[1]>hs.shape[1]-8: continue
            ov=cv2.matchTemplate(hs if front else ms,(TH1>0.25).astype(np.float32),cv2.TM_CCORR)+cv2.matchTemplate(hs,(TS1>0.25).astype(np.float32),cv2.TM_CCORR)
            mg=4; ys,xs=np.where(ov[mg:-mg or None,mg:-mg or None]<0.5)
            if len(xs):
                ys,xs=ys+mg,xs+mg
                d=np.abs(xs*D-60)+np.abs((hs.shape[0]-ys-TH1.shape[0])*D-40)*1.5 if front else np.abs(xs*D-135*sc)+np.abs(ys*D-48)*1.5
                i=int(np.argmin(d)); return dict(s=round(float(sc),2),x=int(xs[i]*D),y=int(ys[i]*D),front=front)
        return None
    top=search(False); low=search(True)
    best=top if (top and (top['s']>=0.8 or not low or low['s']<top['s']+0.15)) else low
    if best is None: best=dict(s=0.45,x=40,y=20)
    json.dump(best,open(fp,'w')); print('title placement',best); return best
TP=title_place()
HDR=prep_img(R+'/assets/look-c/'+edl.get('header','video-how-to-draw-a.png'),int(779*K*TP['s'])); SUB=prep_img(E+'/subject-aligned.png',int(779*K*TP['s']))
P0=DUR*PK/PN; P1=DUR*(PK+1)/PN; N0=int(round(P0*FPS)); N1=int(round(P1*FPS))
R0,R1=RF(N0),RF(max(N0,N1-1))+1
dec=subprocess.Popen(['ffmpeg','-v','error','-ss',str(a+prep['offset']+R0/FPS),'-t',str((R1-R0)/FPS+0.5),'-i',prep['front'],'-vf',vf,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE,bufsize=SW*SH*3)
dal=subprocess.Popen(['ffmpeg','-v','error','-i',E+'/intro_alpha.mp4','-vf',f'select=gte(n\\,{R0})','-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{OW}x{OH}','-r','24','-i','-','-c:v','libx264','-preset','veryfast','-crf','17' if K==1 else '20','-pix_fmt','yuv420p','-y',W+f'/vo/intro_p{PK}.tmp.mp4'],stdin=subprocess.PIPE)
n=N0; TH,TS,TO=ti['t_header_local'],ti['t_subject_local'],ti['t_out_local']; pos=R0-1
while True:
    if n>=N1: break
    while pos<RF(n):   # read forward to this output frame's raw frame (drops the frames inside cut ranges)
        bb=dec.stdout.read(SW*SH*3); aa=dal.stdout.read(1920*1080); pos+=1
        if len(bb)<SW*SH*3 or len(aa)<1920*1080: break
    if len(bb)<SW*SH*3 or len(aa)<1920*1080: break
    f=np.frombuffer(bb,np.uint8).reshape(SH,SW,3); al=np.frombuffer(aa,np.uint8).reshape(1080,1920)
    t=n/FPS; z,cx,cy=face_safe(*cam(t),edl.get('head_boxes')); cw,ch=SW/z,SH/z; x=min(max(cx*SW-cw/2,0),SW-cw); y=min(max(cy*SH-ch/2,0),SH-ch); s=OW/cw
    src=cv2.GaussianBlur(f,(0,0),0.42/s) if 1/s>1.25 else f
    out=cv2.warpAffine(src,np.float32([[s,0,-x*s],[0,s,-y*s]]),(OW,OH),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    A=cv2.warpAffine(al,np.float32([[2*s,0,-x*s],[0,2*s,-y*s]]),(OW,OH),flags=cv2.INTER_LINEAR).astype(np.float32)[...,None]/255
    bg=cv2.GaussianBlur(out,(0,0),3)*0.86
    if z<1.06 and TH<=t<=TO+0.4:
        fo=1-min(1,max(0,(t-TO)/0.35)); X0=-HDR[1].shape[1]-20*K; hx=int(X0+(TP['x']*K-X0)*back((t-TH)/0.45))
        if not TP.get('front'): bg=paste(bg,HDR,hx,TP['y']*K,fo)
    comp=bg*(1-A)+out*A
    if TP.get('front') and z<1.06 and TH<=t<=TO+0.4: comp=paste(comp,HDR,hx,TP['y']*K,fo)                      # header sits behind the people (text-behind look)
    if z<1.06 and TS<=t<=TO+0.4:              # subject word always in front so it stays readable
        fo=1-min(1,max(0,(t-TO)/0.35)); sc=0.2+0.8*back(min(1,(t-TS)/0.4)); c,a2=SUB; w=max(2,int(a2.shape[1]*sc)); h=max(2,int(a2.shape[0]*sc))
        comp=paste(comp,(cv2.resize(c,(w,h)),cv2.resize(a2,(w,h))[...,None]),TP['x']*K+HDR[1].shape[1]//2-w//2,int((TP['y']+184*TP['s'])*K)+SUB[1].shape[0]//2-h//2,fo)
    enc.stdin.write(np.clip(comp,0,255).astype(np.uint8).tobytes()); n+=1
enc.stdin.close(); enc.wait(); os.rename(W+f'/vo/intro_p{PK}.tmp.mp4',W+f'/vo/intro_p{PK}.mp4'); print('intro part',PK,'frames',n-N0)
if all(os.path.exists(W+f'/vo/intro_p{k}.mp4') for k in range(PN)):
    open(W+'/intro_list.txt','w').write(''.join(f"file '{W}/vo/intro_p{k}.mp4'\n" for k in range(PN)))
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','0','-i',W+'/intro_list.txt','-c','copy','-y',W+'/vo/intro.mp4'])
    for k in range(PN): os.remove(W+f'/vo/intro_p{k}.mp4')
    print('intro joined')
