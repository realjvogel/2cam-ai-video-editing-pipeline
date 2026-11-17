"""Head boxes for face-safe punch-ins: detect faces on ~10 front-camera frames spread over the intro and return,
for the left and right person, the box their head occupies at any time (normalised source coords, with margin).
usage: python3 head_boxes.py <frames_dir> <prefix> [haar_dir]   -> prints JSON {"kid":[x0,y0,x1,y1],"adult":[...]}
Frames: <prefix>_0.jpg ... (960x540, already flipped upright). Left/right is mapped to kid/adult by the caller."""
import sys, glob, json, cv2, numpy as np
d,pre=sys.argv[1],sys.argv[2]; hd=sys.argv[3] if len(sys.argv)>3 else '.'
fc=cv2.CascadeClassifier(hd+'/haar_frontalface_default.xml'); pf=cv2.CascadeClassifier(hd+'/haar_profileface.xml')
pts=[]
for f in sorted(glob.glob(f'{d}/{pre}_*.jpg')):
    g=cv2.cvtColor(cv2.imread(f),cv2.COLOR_BGR2GRAY); H,W=g.shape
    for c,fl in ((fc,0),(pf,0),(pf,1)):
        gg=cv2.flip(g,1) if fl else g
        for x,y,w,h in c.detectMultiScale(gg,1.1,5,minSize=(W//20,W//20)):
            cx=(x+w/2)/W; cx=1-cx if fl else cx
            if (y+h/2)/H<0.75: pts.append((cx,(y+h/2)/H,w/W))
P=np.array(pts); out={}
for side,sel in (('left',P[:,0]<0.5),('right',P[:,0]>=0.5)):
    A=P[sel]
    if not len(A): continue
    fw=float(np.median(A[:,2])); x0,x1=np.percentile(A[:,0],[5,95]); y0,y1=np.percentile(A[:,1],[5,95]); fh=fw*16/9
    out[side]=[round(max(0,x0-0.75*fw),3),round(max(0,y0-1.1*fh),3),round(min(1,x1+0.75*fw),3),round(min(1,y1+0.8*fh),3)]
print(json.dumps(out))
