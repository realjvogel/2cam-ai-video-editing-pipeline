"""Thumbnail on a clean generated plate: drawings multiplied onto the blank sheets, then 'How to draw a' + subject + wordmark composited on top.
usage: thumbnail_v2.py <plate.png> <drawing_0.png> <drawing_1.png> <subject-aligned.png> <out.jpg>"""
import sys, cv2, numpy as np
from PIL import Image
src=open('/home/claude/sabtools/thumbnails.py').read(); exec(src[src.index('def sheets') if 'def sheets' in src else 0:src.index('d0,d1,sp,pre')].split("sys.path")[-1].split("A='")[0]) if False else None
exec(open('/home/claude/lookc/compose3.py').read().split('L=json.load')[0].split("arts=")[0].replace("A='look-c-fixed-assets/'",""))
exec(open('/home/claude/lookc/compose3.py').read()[open('/home/claude/lookc/compose3.py').read().index('def sheets'):open('/home/claude/lookc/compose3.py').read().index('L=json.load')])
t=open('/home/claude/sabtools/thumbnails.py').read(); exec(t[t.index('def prewhite'):t.index('def fix_band')])
A='/home/claude/lookc/look-c-fixed-assets/'
plate,d0,d1,subp,out=sys.argv[1:6]; HDRF=sys.argv[6] if len(sys.argv)>6 else 'video-how-to-draw-a.png'
p=cv2.imread(plate); H,W=p.shape[:2]; ch=int(W*9/16); p=cv2.resize(p[0:ch],(1280,720),interpolation=cv2.INTER_AREA)   # keep the top: room for the header
rs=sheets(p)
# the subject word sits bottom-centre: fit each drawing into the part of its sheet above it, so feet/shoes stay visible
_s=Image.open(subp).convert('RGBA'); _a=np.asarray(_s)[...,3]; _ys,_xs=np.where(_a>40); _asp=(_xs.max()-_xs.min()+1)/(_ys.max()-_ys.min()+1); SUBJ_W=int(min(640,230*_asp)); _h=SUBJ_W/_asp   # short words (DOG) are capped at 230 px tall
SUBJ_TOP=712-_h
def above(r,limit):
    (cx,cy),(w,h),ang=r; vert_h=h if (ang%90)<45 else w; top=cy-vert_h/2; bot=min(cy+vert_h/2,limit-6)
    if bot>=cy+vert_h/2-1: return r
    nh=max(bot-top,vert_h*0.55); ncy=top+nh/2
    return ((cx,ncy),(w,nh) if (ang%90)<45 else (nh,h),ang)
rs=[above(r,SUBJ_TOP) for r in rs]
for art,r in zip([prewhite(cv2.imread(d0)),prewhite(cv2.imread(d1))],rs):
    p=place(p,art,r,fill=0.97)                                           # drawings fill the uncovered part of each sheet
c=Image.fromarray(cv2.cvtColor(p,cv2.COLOR_BGR2RGB)).convert('RGBA')
def put(path,w,xy,anchor='tl'):
    im=Image.open(path).convert('RGBA'); a=np.asarray(im)[...,3]; ys,xs=np.where(a>40); im=im.crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1))
    im=im.resize((w,int(im.height*w/im.width)),Image.LANCZOS); x,y=xy
    if anchor=='tc': x-=im.width//2
    if anchor=='bc': x-=im.width//2; y-=im.height
    c.alpha_composite(im,(int(x),int(y))); return im.size
put(A+'super-art-bros-wordmark-light.png',190,(22,16))
put(A+HDRF,520 if HDRF.endswith('-a.png') else 440,(650,8),'tc')
put(subp,SUBJ_W,(640,712),'bc')
c.convert('RGB').save(out,quality=93); print('ok',[(tuple(map(int,r[0])),tuple(map(int,r[1])),round(r[2],1)) for r in rs])
