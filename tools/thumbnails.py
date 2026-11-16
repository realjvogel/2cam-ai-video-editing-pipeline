"""YouTube thumbnails (Look C wood + yellow plates): real drawings multiplied onto the sheets, subject word at the bottom.
usage: thumbnails.py <drawing_0.png> <drawing_1.png> <subject_raw.png> <out_prefix>"""
import sys, cv2, numpy as np, json
from PIL import Image
sys.path.insert(0,'/home/claude/lookc')
A='/home/claude/lookc/look-c-fixed-assets/'
src=open('/home/claude/lookc/compose3.py').read(); exec(src[src.index('def sheets'):src.index('L=json.load')])
def prewhite(a):
    # paper → pure white so no grey box/edge lines show after the multiply: lift low-saturation light pixels, feather + clear the borders
    hsv=cv2.cvtColor(a,cv2.COLOR_BGR2HSV).astype(np.float32); v,sat=hsv[...,2],hsv[...,1]
    k=np.clip((v-200)/30,0,1)*np.clip((60-sat)/30,0,1)            # 1 = paper
    a=a.astype(np.float32); a=a*(1-k[...,None])+255*k[...,None]
    g=(a.min(2)>110)&(a.max(2)<246)&(np.ptp(a,2)<30)                                  # stray paper/stack edges: long straight thin lines near the borders
    Hh,Ww=g.shape; bz=np.zeros_like(g); b=int(0.10*min(Hh,Ww)); bz[:b]=bz[-b:]=True; bz[:,:b]=bz[:,-b:]=True; g&=bz
    ls=cv2.HoughLinesP(g.astype(np.uint8)*255,1,np.pi/720,int(0.1*min(Hh,Ww)),minLineLength=int(0.15*min(Hh,Ww)),maxLineGap=12)
    m=np.zeros((Hh,Ww),np.uint8)
    for x0,y0,x1,y1 in ([] if ls is None else ls.reshape(-1,4)): cv2.line(m,(int(x0),int(y0)),(int(x1),int(y1)),255,7)
    a[(m>0)&g]=255
    H,W=a.shape[:2]; yy,xx=np.mgrid[0:H,0:W]; d=np.minimum(np.minimum(xx,W-1-xx),np.minimum(yy,H-1-yy))/min(H,W)
    e=np.clip((d-0.025)/0.02,0,1)[...,None]                       # outer 1.2% cleared, next 2.5% faded to white
    paperish=((a.min(2)>110)&(np.ptp(a,2)<35))[...,None]                 # only paper/edge greys get cleared at the borders; ink and colour stay
    e=np.where(paperish,e,1.0)
    return (a*e+255*(1-e)).astype(np.uint8)
def fix_band(p):
    # the wood plate's blue title band stops short under the markers: extend it across the full width behind them
    hsv=cv2.cvtColor(p,cv2.COLOR_BGR2HSV); H,W=p.shape[:2]
    col=(hsv[:120,600,0]>95)&(hsv[:120,600,0]<108)&(hsv[:120,600,1]>80); y1=int(np.where(col)[0].max())+1
    mk=((hsv[:y1,:,2]<100)&(hsv[:y1,:,1]<90))|((hsv[:y1,:,1]>150)&(hsv[:y1,:,2]>120)&~((hsv[:y1,:,0]>=5)&(hsv[:y1,:,0]<=20)))                          # marker bodies (dark) + caps (saturated)
    mk=cv2.morphologyEx(mk.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    n,lab,st,_=cv2.connectedComponentsWithStats(mk); keep=np.isin(lab,[i for i in range(1,n) if st[i,4]>400]); keep=cv2.morphologyEx(keep.astype(np.uint8),cv2.MORPH_CLOSE,np.ones((15,15),np.uint8))
    inv=(1-keep).astype(np.uint8); n2,l2,st2,_=cv2.connectedComponentsWithStats(inv)
    for i in range(1,n2):                                              # fill holes inside markers (shaded caps)
        x,y,w,h,a_=st2[i]
        if x>0 and y>0 and x+w<inv.shape[1] and y+h<inv.shape[0] and a_<3000: keep[l2==i]=1
    keep=cv2.dilate(keep,np.ones((3,3),np.uint8)).astype(bool)
    wood=~keep; wood[:,:1000]=False   # only the right end (keeps the wordmark untouched)
    sh=cv2.GaussianBlur(np.roll(np.roll(keep.astype(np.float32),6,0),6,1),(0,0),5)*0.28   # soft drop shadow of the markers on the band
    isb=(hsv[:y1,:,0]>95)&(hsv[:y1,:,0]<108)&(hsv[:y1,:,1]>80); row=np.array([np.median(p[r][isb[r]],0) if isb[r].sum()>20 else p[r,40] for r in range(y1)])
    blue=np.repeat(row[:,None,:],W,1).astype(np.float32)*(1-sh[...,None]); p[:y1][wood]=blue[wood].astype(np.uint8); return p
d0,d1,sp,pre=sys.argv[1:5]; arts=[prewhite(cv2.imread(d0)),prewhite(cv2.imread(d1))]; L=json.load(open(A+'layout.json'))
s=Image.open(sp).convert('RGBA'); a=np.asarray(s)[...,3]; ys,xs=np.where(a>40); subj=s.crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1))
for name,file,key,wf in (('wood',L['thumbnailBlue']['variants']['a'],'thumbnailBlue',0.82),('yellow',L['thumbnail']['variants']['a'],'thumbnail',0.56)):
    p=cv2.imread(A+file)
    if name=='wood': p=fix_band(p)
    for art,r in zip(arts,sheets(p)): p=place(p,art,r)
    c=Image.fromarray(cv2.cvtColor(p,cv2.COLOR_BGR2RGB)).convert('RGBA'); x,y,bw,bh=L[key]['subjectBox_xywh']
    r=bw*wf/subj.width; t=subj.resize((int(subj.width*r),int(subj.height*r)),Image.LANCZOS); c.alpha_composite(t,(x+(bw-t.width)//2,c.height-t.height-14))
    c.convert('RGB').save(f'{pre}-{name}.jpg',quality=92); print(name,c.size)
