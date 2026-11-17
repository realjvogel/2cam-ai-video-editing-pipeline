"""Per-paper hand coverage (is someone's hand on that sheet), second by second.
usage: python3 sab_sides.py <slug> [budget_s]   -> <work>/sides.json  [[t, hand_L, hand_R], ...] (t = raw overhead second)
Resumable: extracts 1 fps overhead frames (320 px, keyframes) for the detail-zoom windows into <work>/top/, then measures
how much of each paper box is covered by something that isn't paper (a hand). The adult only has a
hand on his own sheet while he draws, so it tells the camera when the demo is happening."""
import os, sys, json, time, glob, subprocess
import numpy as np, cv2
slug=sys.argv[1]; BUD=float(sys.argv[2]) if len(sys.argv)>2 else 160; T0=time.time()
SSD=os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')); E=f'{SSD}/SAB-production/episodes/{slug}'
W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug); D=W+'/top'; os.makedirs(D,exist_ok=True)
pj=W+'/prep.json' if os.path.exists(W+'/prep.json') else E+'/prep.json'; st=json.load(open(pj))
top=st['top'];
if not os.path.exists(top): top=SSD+top.split('data drive',1)[1]
cfg=json.load(open(W+'/episode.json')); spans=[(max(1,int(z['t_in'])-3),int(z['t_out'])+3) for z in cfg.get('zooms',[])]
for x,y in spans:   # only the seconds inside detail-zoom windows are needed
    if all(os.path.exists(D+'/%04d.jpg'%t) for t in range(x,y+1)): continue
    if time.time()-T0>BUD-25: break
    subprocess.run(['timeout',str(int(BUD-(time.time()-T0)-8)),'ffmpeg','-nostdin','-v','error','-ss',str(x-1),'-skip_frame','nokey','-i',top,'-t',str(y-x+2),
                    '-vf','fps=1,scale=320:-2','-q:v','5','-start_number',str(x),'-y',D+'/%04d.jpg'])
need=[t for x,y in spans for t in range(x,y+1)]; have=[t for t in need if os.path.exists(D+'/%04d.jpg'%t)]
print('frames',len(have),'/',len(need))
if len(have)<len(need): sys.exit(0)
fs=sorted(glob.glob(D+'/*.jpg')); P=np.array(json.load(open(W+'/papers.json'))); T=np.arange(max(int(os.path.basename(f)[:4]) for f in fs)+3)
B=np.stack([np.interp(T,P[:,0],P[:,1+j]) for j in range(8)],1)
out=[]
for f in fs:   # hand coverage: share of each paper box (shrunk 4%) that isn't paper
    im=cv2.imread(f); h,w=im.shape[:2]; hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    notpaper=(hsv[...,1]>55)|(hsv[...,2]<120); i=int(os.path.basename(f)[:4])-1; row=[i+1]
    for k in (0,4):
        x0,y0,x1,y1=B[i+1,k:k+4]; mx,my=0.04*(x1-x0),0.04*(y1-y0)
        a,b,c,e=int((x0+mx)*w),int((y0+my)*h),int((x1-mx)*w),int((y1-my)*h)
        row.append(float(notpaper[b:e,a:c].mean()) if e>b and c>a else 0.0)
    out.append(row)
json.dump(out,open(W+'/sides.json','w')); print('SIDES DONE',len(out))
