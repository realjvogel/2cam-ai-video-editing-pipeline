"""QA, part 1 (device): measure a finished episode and pull the review material. Resumable; rerun until it prints DONE.
usage: sab_qa.py <final.mp4> <qa_dir> [budget_s]
writes: meta.json, audio.json (loudness + silences), chunks/<k>.json (cuts, black, frozen), frames/t<sec>.jpg (1 fps), cuts/c<i>_<a|b|c>.jpg, speech16k.wav"""
import json, os, re, subprocess, sys, time
src,out=sys.argv[1],sys.argv[2]; BUD=float(sys.argv[3]) if len(sys.argv)>3 else 150; T0=time.time(); CH=60
os.makedirs(out+'/chunks',exist_ok=True); os.makedirs(out+'/frames',exist_ok=True); os.makedirs(out+'/cuts',exist_ok=True)
def left(): return BUD-(time.time()-T0)
def probe(*a): return subprocess.run(['ffprobe','-v','error']+list(a)+[src],capture_output=True,text=True).stdout
mp=out+'/meta.json'
if not os.path.exists(mp):
    v=probe('-select_streams','v','-show_entries','stream=duration,width,height,r_frame_rate','-of','json'); a=probe('-select_streams','a','-show_entries','stream=duration','-of','json')
    vs=json.loads(v)['streams'][0]; asd=float(json.loads(a)['streams'][0]['duration'])
    json.dump(dict(file=os.path.basename(src),video_s=float(vs['duration']),audio_s=asd,width=vs['width'],height=vs['height'],fps=vs['r_frame_rate']),open(mp,'w'),indent=1)
M=json.load(open(mp)); D=M['video_s']
ap=out+'/audio.json'
if not os.path.exists(ap):
    r=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-i',src,'-vn','-af','silencedetect=n=-45dB:d=0.6,ebur128=peak=true','-f','null','-'],capture_output=True,text=True).stderr
    sil=[]; st=None
    for l in r.splitlines():
        m=re.search(r'silence_start: ([\d.]+)',l)
        if m: st=float(m.group(1))
        m=re.search(r'silence_end: ([\d.]+)',l)
        if m and st is not None: sil.append([round(st,2),round(float(m.group(1)),2)]); st=None
    I=re.findall(r'I:\s+(-?[\d.]+) LUFS',r); TP=re.findall(r'Peak:\s+(-?[\d.]+) dBFS',r)
    json.dump(dict(integrated_lufs=float(I[-1]) if I else None,true_peak_dbtp=float(TP[-1]) if TP else None,silences=sil),open(ap,'w'),indent=1)
    subprocess.run(['ffmpeg','-nostdin','-v','error','-i',src,'-vn','-ac','1','-ar','16000','-y',out+'/speech16k.wav'])
k=0
while k*CH<D:
    cp=f'{out}/chunks/{k:03d}.json'
    if not os.path.exists(cp):
        if left()<45: print('PARTIAL',k); sys.exit(0)
        t0=k*CH; dur=min(CH,D-t0)
        fc=(f"[0:v]scale=480:270,split=2[a][b];[a]fps=1,setpts=PTS-STARTPTS[f];"
            f"[b]blackdetect=d=0.25:pix_th=0.06,freezedetect=n=0.003:d=2.5,select='gt(scene\\,0.32)',metadata=print:file={out}/chunks/{k:03d}.scenes[s]")
        r=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-ss',str(t0),'-t',str(dur),'-i',src,'-filter_complex',fc,'-map','[f]','-q:v','4','-start_number','0',f'{out}/frames/k{k:03d}_%03d.jpg','-map','[s]','-f','null','-'],capture_output=True,text=True).stderr
        cuts=[round(t0+float(m),3) for m in re.findall(r'pts_time:([\d.]+)',open(f'{out}/chunks/{k:03d}.scenes').read())]
        blk=[[round(t0+float(a),2),round(t0+float(b),2)] for a,b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)',r)]
        frz=[round(t0+float(a),2) for a in re.findall(r'freeze_start: ([\d.]+)',r)]
        for f in sorted(os.listdir(out+'/frames')):
            m=re.match(rf'k{k:03d}_(\d+)\.jpg',f)
            if m: os.replace(f'{out}/frames/{f}',f"{out}/frames/t{t0+int(m.group(1)):05d}.jpg")
        json.dump(dict(t0=t0,cuts=cuts,black=blk,frozen=frz),open(cp,'w'))
        print('chunk',k,'cuts',len(cuts),round(time.time()-T0),flush=True)
    k+=1
cuts=sorted(c for f in sorted(os.listdir(out+'/chunks')) if f.endswith('.json') for c in json.load(open(f'{out}/chunks/{f}'))['cuts'])
for i,c in enumerate(cuts):
    if os.path.exists(f'{out}/cuts/c{i:03d}_c.jpg'): continue
    if left()<15: print('PARTIAL cuts',i); sys.exit(0)
    for tag,t in (('a',c-0.5),('b',c+0.08),('c',c+0.6)):
        subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(max(0,t)),'-i',src,'-frames:v','1','-vf','scale=480:270','-q:v','4','-y',f'{out}/cuts/c{i:03d}_{tag}.jpg'])
json.dump(cuts,open(out+'/cuts.json','w')); print('DONE cuts',len(cuts))
# ---- pack: contact sheets for the reviewer (run after DONE) ----
if len(sys.argv)>4 and sys.argv[4]=='pack':
    import cv2, numpy as np, glob, shutil
    P=out+'/pack'; os.makedirs(P,exist_ok=True)
    fr=sorted(glob.glob(out+'/frames/t*.jpg')); W_,H_=320,180
    def lab(im,txt):
        im=cv2.resize(im,(W_,H_)); cv2.rectangle(im,(0,0),(78,22),(0,0,0),-1); cv2.putText(im,txt,(4,16),cv2.FONT_HERSHEY_SIMPLEX,0.5,(255,255,255),1); return im
    for s in range(0,len(fr),30):
        ims=[lab(cv2.imread(f),'%d:%02d'%(int(f[-9:-4])//60,int(f[-9:-4])%60)) for f in fr[s:s+30]]
        while len(ims)%6: ims.append(np.zeros((H_,W_,3),np.uint8))
        cv2.imwrite(f'{P}/sheet_{s:05d}.jpg',np.vstack([np.hstack(ims[i:i+6]) for i in range(0,len(ims),6)]),[cv2.IMWRITE_JPEG_QUALITY,82])
    cuts=json.load(open(out+'/cuts.json'))
    for s in range(0,len(cuts),8):
        rows=[]
        for i in range(s,min(s+8,len(cuts))):
            c=cuts[i]; rows.append(np.hstack([lab(cv2.imread(f'{out}/cuts/c{i:03d}_{t}.jpg'),('%d:%05.2f'%(c//60,c%60))+(' '+t)) for t in 'abc']))
        cv2.imwrite(f'{P}/cuts_{s:03d}.jpg',np.vstack(rows),[cv2.IMWRITE_JPEG_QUALITY,82])
    ch=[json.load(open(f)) for f in sorted(glob.glob(out+'/chunks/*.json'))]
    json.dump(dict(meta=json.load(open(out+'/meta.json')),audio=json.load(open(out+'/audio.json')),cuts=cuts,
        black=[b for c in ch for b in c['black']],frozen=[f for c in ch for f in c['frozen']]),open(P+'/measure.json','w'),indent=1)
    shutil.copy(out+'/speech16k.wav',P+'/speech16k.wav')
    for f in fr[:40]: shutil.copy(f,P+'/'+os.path.basename(f))     # full-size 480x270 frames of the opening, for the face/title check
    print('PACKED',len(os.listdir(P)))
