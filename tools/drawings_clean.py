import cv2, numpy as np
exec(open('clean.py').read().split('def cleanup')[0].replace("print(","(lambda *a,**k:None)("))
def cleanup3(p):
    f=p.astype(np.float32); hsv=cv2.cvtColor(p,cv2.COLOR_BGR2HSV)
    paper=((hsv[...,1]<40)&(hsv[...,2]>150)).astype(np.float32)           # only true paper pixels define the lighting
    paper=cv2.erode(paper,np.ones((9,9),np.uint8))
    s=60; num=cv2.GaussianBlur(f*paper[...,None],(0,0),s); den=cv2.GaussianBlur(paper,(0,0),s)[...,None]
    bg=num/np.maximum(den,1e-3)
    flat=np.clip(f/np.maximum(bg,1)*250,0,255)                            # paper -> white; marker colors untouched
    H,W=flat.shape[:2]; b=int(0.05*min(H,W)); flat[:b]=255; flat[-b:]=255; flat[:,:b]=255; flat[:,-b:]=255
    yc=cv2.cvtColor(p,cv2.COLOR_BGR2YCrCb); sk=((yc[...,1]>135)&(yc[...,1]<172)&(yc[...,2]>80)&(yc[...,2]<128)&(yc[...,0]>80)).astype(np.uint8)
    sk[:int(H*0.75)]=0; sk=cv2.dilate(sk,np.ones((61,61),np.uint8)); flat[sk>0]=255
    ink=((255-flat).max(2)>40).astype(np.uint8); ink=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
    ys,xs=np.where(ink>0); x0,x1,y0,y1=np.percentile(xs,.3),np.percentile(xs,99.7),np.percentile(ys,.3),np.percentile(ys,99.7)
    mx,my=(x1-x0)*.05,(y1-y0)*.05
    return flat[int(max(0,y0-my)):int(min(H,y1+my)),int(max(0,x0-mx)):int(min(W,x1+mx))].astype(np.uint8)
from PIL import Image
row=[]
for i in (0,1):
    raw=best[i][2]; new=cleanup3(raw); cv2.imwrite(f'art3_{i}.png',new)
    r=Image.fromarray(cv2.cvtColor(raw,cv2.COLOR_BGR2RGB)); r.thumbnail((560,600)); n=Image.fromarray(cv2.cvtColor(new,cv2.COLOR_BGR2RGB)); n.thumbnail((560,600)); row+=[r,n]
s=Image.new('RGB',(1120,1200),(60,60,60))
for k,im in enumerate(row): s.paste(im,((k%2)*560,(k//2)*600))
s.save('clean_compare3.jpg',quality=88)
