"""Hard-edged diagonal wipe from the intro's last framing (front) to the lesson's base framing (overhead), with a thin cream edge.
usage: sab_wipe.py <slug>   -> W/vo/wipe.mp4"""
import cv2, numpy as np, subprocess, json, os, sys
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from sab_cams import Cams
slug=sys.argv[1]; W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug)
edl=json.load(open(W+'/edl.json')); prep=json.load(open(W+'/prep.json')); K=edl.get('out_k',1); OW,OH,SW,SH=1920*K,1080*K,3840,2160
s=[x for x in edl['segments'] if x['role']=='wipe'][0]; d=s['b']-s['a']; N=int(round(d*24)); C=Cams(W,edl)
z,cx,cy=edl['intro_shots'][-1][3] if edl.get('intro_shots') else (1,.5,.5)
def frames(src,ss,vf):
    p=subprocess.Popen(['ffmpeg','-v','error','-ss',str(ss),'-t',str(d+0.5),'-i',src,'-vf',vf,'-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE); out=[]
    while len(out)<N:
        b=p.stdout.read(SW*SH*3)
        if len(b)<SW*SH*3: break
        out.append(np.frombuffer(b,np.uint8).reshape(SH,SW,3))
    p.kill(); return out
def crop(f,z,cx,cy):
    cw,ch=SW/z,SH/z; x=min(max(cx*SW-cw/2,0),SW-cw); y=min(max(cy*SH-ch/2,0),SH-ch); sc=OW/cw
    return cv2.warpAffine(f,np.float32([[sc,0,-x*sc],[0,sc,-y*sc]]),(OW,OH),flags=cv2.INTER_LINEAR)
F=frames(prep['front'],s['a']+prep['offset'],('hflip,vflip,' if prep['flip_front'] else '')+'fps=24')
T=frames(prep['top'],s['top_a'],'fps=24')
while len(F)<N: F.append(F[-1])
while len(T)<N: T.append(T[-1])
yy,xx=np.mgrid[0:OH,0:OW].astype(np.float32); diag=(xx/OW+yy/OH)/2          # 0 at top-left, 1 at bottom-right
enc=subprocess.Popen(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{OW}x{OH}','-r','24','-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','18' if K==1 else '20','-pix_fmt','yuv420p','-y',W+'/vo/wipe.tmp.mp4'],stdin=subprocess.PIPE)
cream=np.array([200,226,240],np.float32); ew=0.006
for k in range(N):
    p=k/(N-1); p=p*p*(3-2*p); e=-0.05+1.1*p                                  # edge position sweeps past both corners
    a=crop(F[k],z,cx,cy).astype(np.float32); b=crop(T[k],*C.base(s['top_a']+k/24)).astype(np.float32)
    m=np.clip((e-diag)/0.002,0,1)[...,None]; line=(np.abs(diag-e)<ew)[...,None]
    o=a*(1-m)+b*m; o=np.where(line,cream,o)
    enc.stdin.write(o.astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); os.rename(W+'/vo/wipe.tmp.mp4',W+'/vo/wipe.mp4'); print('wipe frames',N)
