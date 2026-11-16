"""Crop a generated subject word (alpha>40) and rotate it so its baseline slant matches the 'How to draw a' header; width 779.
usage: title_align.py <subject.png> <header.png> <out.png>"""
import sys, numpy as np
from PIL import Image
def crop(im):
    a=np.asarray(im)[...,3]; ys,xs=np.where(a>40); return im.crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1))
def angle(im):
    a=np.asarray(im)[...,3]>40; xs=[];ys=[]
    for x in range(0,a.shape[1],4):
        c=np.where(a[:,x])[0]
        if len(c): xs.append(x); ys.append(c.max())
    xs,ys=np.array(xs),np.array(ys); k=np.polyfit(xs,ys,1); r=ys-np.polyval(k,xs); m=r>-np.percentile(np.abs(r),70)
    return np.degrees(np.arctan(np.polyfit(xs[m],ys[m],1)[0]))
S=crop(Image.open(sys.argv[1]).convert('RGBA')); H=crop(Image.open(sys.argv[2]).convert('RGBA')); aH=angle(H)
for _ in range(4):
    d=angle(S)-aH
    if abs(d)<0.15: break
    S=crop(S.rotate(d,resample=Image.BICUBIC,expand=True))
S=S.resize((779,int(S.height*779/S.width)),Image.LANCZOS); S.save(sys.argv[3]); print('header %.2f subject %.2f size'%(aH,angle(S)),S.size)
