"""Extract + clean the two finished drawings from late overhead frames.
usage: drawings_extract.py <frames_dir> <out_dir>   (frames named top_<sec>.jpg; picks the latest frame per paper with no skin)"""
import cv2, numpy as np, glob, re, sys, os


def papers(im):
    h,w=im.shape[:2]; hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    m=((hsv[...,1]<30)&(hsv[...,2]>190)).astype(np.uint8)*255; m=cv2.morphologyEx(m,cv2.MORPH_OPEN,np.ones((9,9),np.uint8))
    m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,np.ones((41,41),np.uint8))
    cs,_=cv2.findContours(m,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    out=[]
    for c in cs:
        a=cv2.contourArea(c)
        if 0.08*w*h<a<0.25*w*h: out.append(c)
        elif 0.25*w*h<=a<0.5*w*h:            # two sheets touching: split at the weakest column (the seam) near the middle
            x,y,bw,bh=cv2.boundingRect(c)
            if bw<1.2*bh: continue
            sub=np.zeros((h,w),np.uint8); cv2.drawContours(sub,[c],-1,255,-1)
            raw=(((hsv[...,1]<30)&(hsv[...,2]>190))&(sub>0)).astype(np.float32)
            col=raw[y:y+bh,x:x+bw].mean(0); lo,hi=int(bw*.35),int(bw*.65); cut=x+lo+int(np.argmin(np.convolve(col[lo:hi],np.ones(15)/15,'same')))
            for x0,x1 in ((x,cut-4),(cut+4,x+bw)):
                part=sub.copy(); part[:,:x0]=0; part[:,x1:]=0
                cc,_=cv2.findContours(part,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
                if cc: out.append(max(cc,key=cv2.contourArea))
    return sorted(out,key=lambda c:cv2.boundingRect(c)[0])
def warp(im,c):
    box=cv2.boxPoints(cv2.minAreaRect(c)); s=box.sum(1); d=np.diff(box,axis=1)[:,0]
    tl,br,tr,bl=box[s.argmin()],box[s.argmax()],box[d.argmin()],box[d.argmax()]
    W=int(np.linalg.norm(tr-tl)); H=int(np.linalg.norm(bl-tl))
    M=cv2.getPerspectiveTransform(np.float32([tl,tr,br,bl]),np.float32([[0,0],[W,0],[W,H],[0,H]]))
    o=cv2.warpPerspective(im,M,(W,H)); k=int(min(W,H)*0.012); return o[k:-k,k:-k]
def skin(p):
    y=cv2.cvtColor(p,cv2.COLOR_BGR2YCrCb); m=(y[...,1]>140)&(y[...,1]<175)&(y[...,2]>85)&(y[...,2]<125)&(y[...,0]>60)
    H,W=m.shape; b=int(0.12*min(H,W)); edge=np.ones_like(m); edge[b:-b,b:-b]=False   # hands enter from the edges; drawing colors live inside
    return m[edge].mean()

def glare(p):   # blown-out highlights inside the drawing (light reflecting off wet marker)
    H,W=p.shape[:2]; c=p[int(H*.15):int(H*.85),int(W*.15):int(W*.85)]; return float((c.min(2)>=250).mean())
def cleanup3(p,fingers=True):
    f=p.astype(np.float32); hsv=cv2.cvtColor(p,cv2.COLOR_BGR2HSV)
    paper=((hsv[...,1]<40)&(hsv[...,2]>150)).astype(np.float32)           # only true paper pixels define the lighting
    paper=cv2.erode(paper,np.ones((9,9),np.uint8))
    s=60; num=cv2.GaussianBlur(f*paper[...,None],(0,0),s); den=cv2.GaussianBlur(paper,(0,0),s)[...,None]
    bg=num/np.maximum(den,1e-3)
    # big colored areas have no paper nearby: fall back to a wider estimate, then the global paper level, so the light estimate never collapses
    num2=cv2.GaussianBlur(f*paper[...,None],(0,0),s*4); den2=cv2.GaussianBlur(paper,(0,0),s*4)[...,None]; bg2=num2/np.maximum(den2,1e-3)
    glob_=np.median(f[paper>0],0) if paper.sum()>100 else np.array([235,235,235],np.float32)
    w1=np.clip(den/0.08,0,1); w2=np.clip(den2/0.08,0,1)
    bg=bg*w1+(bg2*w2+glob_*(1-w2))*(1-w1)
    flat=np.clip(f/np.maximum(bg,1)*250,0,255)                            # paper -> white; marker colors untouched
    H,W=flat.shape[:2]; b=int(0.02*min(H,W)); flat[:b]=255; flat[-b:]=255; flat[:,:b]=255; flat[:,-b:]=255
    yc=cv2.cvtColor(p,cv2.COLOR_BGR2YCrCb); sk=((yc[...,1]>135)&(yc[...,1]<172)&(yc[...,2]>80)&(yc[...,2]<128)&(yc[...,0]>80)).astype(np.uint8)
    sk[:int(H*0.75)]=0; sk=cv2.dilate(sk,np.ones((61,61),np.uint8))
    if fingers: flat[sk>0]=255
    ink=((255-flat).max(2)>40).astype(np.uint8); ink=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
    ys,xs=np.where(ink>0); x0,x1,y0,y1=np.percentile(xs,.05),np.percentile(xs,99.95),np.percentile(ys,.05),np.percentile(ys,99.95)
    mx,my=(x1-x0)*.05,(y1-y0)*.05
    return flat[int(max(0,y0-my)):int(min(H,y1+my)),int(max(0,x0-mx)):int(min(W,x1+mx))].astype(np.uint8)

SRC,OUT=sys.argv[1],sys.argv[2]; cands={0:[],1:[]}
for f in sorted(glob.glob(SRC+'/top_*.jpg'),key=lambda s:int(re.findall(r'_(\d+)',s)[-1])):
    t=int(re.findall(r'_(\d+)',f)[-1]); im=cv2.imread(f); ps=papers(im)
    if len(ps)!=2: print(t,'papers',len(ps)); continue
    for i,c in enumerate(ps): p=warp(im,c); cands[i].append((skin(p),t,p))
for i in (0,1):
    print('side',i,[(t,round(s,4)) for s,t,_ in cands[i]])
    mn=min(x[0] for x in cands[i]); ok=[x for x in cands[i] if x[0]<=max(0.002,1.5*mn)]
    g=[glare(x[2]) for x in ok]; gm=min(g); ok=[x for x,gg in zip(ok,g) if gg<=gm*1.5+0.0005]; print('  glare min',round(gm,4))
    s,t,p=max(ok,key=lambda x:x[1]); print(' -> using',t)
    cv2.imwrite(os.path.join(OUT,f'drawing_{i}.png'),cleanup3(p,fingers=s>0.03))
