"""Animated outro: drawings composited onto the sheets in Josh's outro clip (first 3 s looped to 12 s) + Keep Drawing lettering.
usage: outro_animate.py <drawing_0.png> <drawing_1.png> <out.mp4>"""
import cv2, numpy as np, glob, subprocess
from PIL import Image
fs=sorted(glob.glob('/home/claude/outro_vid/f/*.png')); F=[cv2.imread(f) for f in fs]; H,W=F[0].shape[:2]
rects=[(393,263,535,517),(977,263,539,516)]
import sys; ART0,ART1,OUTP=sys.argv[1],sys.argv[2],sys.argv[3]
arts=[cv2.imread(ART0),cv2.imread(ART1)]
layer=np.ones((H,W,3),np.float32)
for art,(x,y,w,h) in zip(arts,rects):
    ah,aw=art.shape[:2]; r=min(w*0.97/aw,h*0.97/ah); a=cv2.resize(art,(int(aw*r),int(ah*r)),interpolation=cv2.INTER_AREA)
    ox=x+(w-a.shape[1])//2; oy=y+(h-a.shape[0])//2; layer[oy:oy+a.shape[0],ox:ox+a.shape[1]]=a/255.0
def text_layer():
    c=Image.new('RGBA',(W,H),(0,0,0,0))
    def put(p,box):
        im=Image.open(p).convert('RGBA'); x,y,bw,bh=box; r=min(bw/im.width,bh/im.height); im=im.resize((int(im.width*r),int(im.height*r)),Image.LANCZOS)
        c.alpha_composite(im,(x+(bw-im.width)//2,y))
    put('/home/claude/lookc/outro_keep-drawing.png',(410,4,1100,200)); put('/home/claude/lookc/outro_thanks.png',(610,196,700,62))
    a=np.asarray(c).astype(np.float32); return a[...,:3][...,::-1],a[...,3:]/255
tc,ta=text_layer()
def comp(fr,t):
    f=fr.astype(np.float32); hsv=cv2.cvtColor(fr,cv2.COLOR_BGR2HSV)
    wm=((hsv[...,1]<40)&(hsv[...,2]>200)).astype(np.uint8)
    n,lab=cv2.connectedComponents(wm,connectivity=4)
    keep=np.zeros_like(wm)
    for x,y,w,h in rects:                                   # the white region containing each sheet's center = the sheet
        for cx,cy in ((x+w//2,y+h//2),(x+w//4,y+h//4),(x+3*w//4,y+h//4)):
            l=lab[cy,cx]
            if l: keep[lab==l]=1
    keep=cv2.dilate(keep,np.ones((3,3),np.uint8))
    m=cv2.GaussianBlur(keep.astype(np.float32),(0,0),0.8)[...,None]
    out=f*(1-m)+f*layer*m
    fa=min(1,t/0.6)                                                  # titles fade in over 0.6 s
    out=out*(1-ta*fa)+tc*ta*fa
    return np.clip(out,0,255).astype(np.uint8)
C=[comp(fr,10) for fr in F]
N=10                         # crossfade frames for the loop seam
unit=[cv2.addWeighted(C[62+i],1-(i+1)/(N+1),C[i],(i+1)/(N+1),0) for i in range(N)]+C[N:62]
seq=C[:62]; total=int(12*24)
while len(seq)<total: seq+=unit
seq=seq[:total]
enc=subprocess.Popen(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r','24','-i','-','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-y',OUTP],stdin=subprocess.PIPE)
for k,fr in enumerate(seq):
    t=k/24
    if t<0.6:  # redo frames with fading titles
        fr=comp(F[k],t)
    if t>11.3: fr=(fr.astype(np.float32)*max(0,(12-t)/0.7)).astype(np.uint8)
    enc.stdin.write(fr.tobytes())
enc.stdin.close(); enc.wait(); print('frames',len(seq))
cv2.imwrite(OUTP+'.check.jpg',cv2.resize(seq[100],(960,540)))
