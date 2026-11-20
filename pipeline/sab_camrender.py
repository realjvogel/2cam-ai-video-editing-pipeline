"""Render a top-camera segment with the SAB virtual camera (smooth sub-pixel zoom + marker-row stabilization).
usage: sab_camrender.py <ep_dir> <edl.json> <src> <ss> <dur> <out>"""
import cv2, numpy as np, subprocess, json, sys, os
from sab_cams import Cams
ep,edlp,src,ss,dur,out=sys.argv[1],sys.argv[2],sys.argv[3],float(sys.argv[4]),float(sys.argv[5]),sys.argv[6]
C=Cams(ep,json.load(open(edlp))); K=json.load(open(edlp)).get('out_k',1); _pp=os.path.join(ep,'prep.json'); _pr=json.load(open(_pp)) if os.path.exists(_pp) else {}; SW,SH,OW,OH,FPS=_pr.get('src_w',3840),_pr.get('src_h',2160),1920*K,1080*K,24; stab=[0.05,0.02,0.95,0.17]
dec=subprocess.Popen(['ffmpeg','-v','error','-ss',str(ss),'-t',str(dur),'-i',src,'-vf','fps=24','-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE,bufsize=SW*SH*3)
enc=subprocess.Popen(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{OW}x{OH}','-r','24','-i','-','-c:v','libx264','-preset','veryfast','-crf','17' if K==1 else '20','-pix_fmt','yuv420p','-y',out],stdin=subprocess.PIPE)
ref=None; prev=(0.0,0.0); hist=[]; n=0
while True:
    b=dec.stdout.read(SW*SH*3)
    if len(b)<SW*SH*3: break
    f=np.frombuffer(b,np.uint8).reshape(SH,SW,3)
    x0,y0,x1,y1=[int(v) for v in (stab[0]*SW,stab[1]*SH,stab[2]*SW,stab[3]*SH)]
    g=cv2.cvtColor(cv2.resize(f[y0:y1,x0:x1],None,fx=0.5,fy=0.5,interpolation=cv2.INTER_AREA),cv2.COLOR_BGR2GRAY).astype(np.float32)
    if ref is None: ref=g; win=cv2.createHanningWindow(g.shape[::-1],cv2.CV_32F)
    (sx,sy),resp=cv2.phaseCorrelate(ref,g,win)
    if resp>0.08 and abs(sx)<20 and abs(sy)<20: prev=(sx*2,sy*2)
    hist.append(prev); dx,dy=np.median(np.array(hist[-5:]),0)
    z,cx,cy=C.cam(ss+n/FPS); cw,ch=SW/z,SH/z
    x=min(max(cx*SW-cw/2,0),SW-cw)+dx; y=min(max(cy*SH-ch/2,0),SH-ch)+dy; s=OW/cw
    srcf=cv2.GaussianBlur(f,(0,0),0.42/s) if 1/s>1.25 else f
    o=cv2.warpAffine(srcf,np.float32([[s,0,-x*s],[0,s,-y*s]]),(OW,OH),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
    enc.stdin.write(o.tobytes()); n+=1
enc.stdin.close(); enc.wait(); print('frames',n)
