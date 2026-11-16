"""Intro: front cam with face-centered punch-ins, softened background, animated Look C title behind the people.
Needs: W/edl.json (intro segment, title timing, punchins), E/intro_alpha.mp4 (person matte of the 1080 proxy), E/subject-aligned.png"""
import cv2, numpy as np, subprocess, json, os, sys
from PIL import Image
slug=sys.argv[1]; PK=int(sys.argv[2]) if len(sys.argv)>2 else 0; PN=int(sys.argv[3]) if len(sys.argv)>3 else 1; SSD=os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')); R=SSD+'/SAB-production'; E=f'{R}/episodes/{slug}'; W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug)
prep=json.load(open(W+'/prep.json')); edl=json.load(open(W+'/edl.json')); seg=[s for s in edl['segments'] if s['role']=='intro'][0]
a,b=seg['a'],seg['b']; DUR=b-a; K=edl.get('out_k',1); SW,SH,OW,OH,FPS=3840,2160,1920*K,1080*K,24; ti=edl['title']
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
P0=DUR*PK/PN; P1=DUR*(PK+1)/PN; N0=int(round(P0*FPS)); N1=int(round(P1*FPS))
dec=subprocess.Popen(['ffmpeg','-v','error','-ss',str(a+prep['offset']+N0/FPS),'-t',str((N1-N0)/FPS+0.5),'-i',prep['front'],'-vf',vf,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE,bufsize=SW*SH*3)
dal=subprocess.Popen(['ffmpeg','-v','error','-i',E+'/intro_alpha.mp4','-vf',f'select=gte(n\\,{N0})','-vsync','0','-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
enc=subprocess.Popen(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{OW}x{OH}','-r','24','-i','-','-c:v','libx264','-preset','veryfast','-crf','17' if K==1 else '20','-pix_fmt','yuv420p','-y',W+f'/vo/intro_p{PK}.tmp.mp4'],stdin=subprocess.PIPE)
n=N0; TH,TS,TO=ti['t_header_local'],ti['t_subject_local'],ti['t_out_local']
while True:
    bb=dec.stdout.read(SW*SH*3); aa=dal.stdout.read(1920*1080)
    if n>=N1 or len(bb)<SW*SH*3 or len(aa)<1920*1080: break
    f=np.frombuffer(bb,np.uint8).reshape(SH,SW,3); al=np.frombuffer(aa,np.uint8).reshape(1080,1920)
    t=n/FPS; z,cx,cy=cam(t); cw,ch=SW/z,SH/z; x=min(max(cx*SW-cw/2,0),SW-cw); y=min(max(cy*SH-ch/2,0),SH-ch); s=OW/cw
    src=cv2.GaussianBlur(f,(0,0),0.42/s) if 1/s>1.25 else f
    out=cv2.warpAffine(src,np.float32([[s,0,-x*s],[0,s,-y*s]]),(OW,OH),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT).astype(np.float32)
    A=cv2.warpAffine(al,np.float32([[2*s,0,-x*s],[0,2*s,-y*s]]),(OW,OH),flags=cv2.INTER_LINEAR).astype(np.float32)[...,None]/255
    bg=cv2.GaussianBlur(out,(0,0),3)*0.86
    if z<1.06 and TH<=t<=TO+0.4:
        fo=1-min(1,max(0,(t-TO)/0.35)); bg=paste(bg,HDR,int((-820+(135+820)*back((t-TH)/0.45))*K),48*K,fo)
    comp=bg*(1-A)+out*A                      # header sits behind the people (text-behind look)
    if z<1.06 and TS<=t<=TO+0.4:              # subject word always in front so it stays readable
        fo=1-min(1,max(0,(t-TO)/0.35)); sc=0.2+0.8*back(min(1,(t-TS)/0.4)); c,a2=SUB; w=max(2,int(a2.shape[1]*sc)); h=max(2,int(a2.shape[0]*sc))
        comp=paste(comp,(cv2.resize(c,(w,h)),cv2.resize(a2,(w,h))[...,None]),135*K+779*K//2-w//2,232*K+SUB[1].shape[0]//2-h//2,fo)
    enc.stdin.write(np.clip(comp,0,255).astype(np.uint8).tobytes()); n+=1
enc.stdin.close(); enc.wait(); os.rename(W+f'/vo/intro_p{PK}.tmp.mp4',W+f'/vo/intro_p{PK}.mp4'); print('intro part',PK,'frames',n-N0)
if all(os.path.exists(W+f'/vo/intro_p{k}.mp4') for k in range(PN)):
    open(W+'/intro_list.txt','w').write(''.join(f"file '{W}/vo/intro_p{k}.mp4'\n" for k in range(PN)))
    subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','0','-i',W+'/intro_list.txt','-c','copy','-y',W+'/vo/intro.mp4'])
    for k in range(PN): os.remove(W+f'/vo/intro_p{k}.mp4')
    print('intro joined')
