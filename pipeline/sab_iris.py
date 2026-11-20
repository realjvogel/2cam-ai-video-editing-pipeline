"""1930s iris: closes on the kid's face (front cam; edl iris_on: kid|adult) to a dot, opens on the outro video. usage: sab_iris.py <slug> <a_raw>"""
import cv2, numpy as np, subprocess, os, sys, json
slug,a=sys.argv[1],float(sys.argv[2]); SSD=os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')); E=f'{SSD}/SAB-production/episodes/{slug}'; W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug)
prep=json.load(open(W+'/prep.json')); edl=json.load(open(W+'/edl.json')); K=edl.get('out_k',1); OW,OH,N=1920*K,1080*K,24
vf=('hflip,vflip,' if prep['flip_front'] else '')+f'scale={OW}:{OH},fps=24'
def frames(cmd):
    p=subprocess.Popen(cmd+['-f','rawvideo','-pix_fmt','bgr24','-'],stdout=subprocess.PIPE); out=[]
    while len(out)<N:
        b=p.stdout.read(OW*OH*3)
        if len(b)<OW*OH*3: break
        out.append(np.frombuffer(b,np.uint8).reshape(OH,OW,3))
    return out
A=frames(['ffmpeg','-v','error','-ss',str(a+prep['offset']),'-t','1.0','-i',prep['front'],'-vf',vf]); B=frames(['ffmpeg','-v','error','-t','1.0','-i',E+'/outro_anim_v.mp4','-vf',f'fps=24,scale={OW}:{OH}:flags=lanczos'])
while len(A)<N: A.append(A[-1])
yy,xx=np.mgrid[0:OH,0:OW]; R=np.hypot(OW,OH)/2+20; _who=edl.get('iris_on','kid'); fx,fy=edl['faces'][_who][0]*OW,edl['faces'][_who][1]*OH   # closes on the kid by default
circ=lambda cx,cy,r:(np.hypot(xx-cx,yy-cy)<=r).astype(np.float32)[...,None]
enc=subprocess.Popen(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{OW}x{OH}','-r','24','-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-y',W+'/vo/iris.mp4.tmp.mp4'],stdin=subprocess.PIPE)
for k in range(N):
    t=k/(N-1)
    # close to a small dot and open straight from one (no held black: QA flags >0.3 s of black)
    if t<0.5: f=A[k]*circ(fx,fy,R*max(0.025,(1-t/0.5)**1.6))
    else: f=B[k]*circ(OW/2,OH/2,R*max(0.025,((t-0.5)/0.5)**1.2))
    enc.stdin.write(f.astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait(); os.rename(W+'/vo/iris.mp4.tmp.mp4',W+'/vo/iris.mp4'); print('iris ok')
