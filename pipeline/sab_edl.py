"""Build edl.json from episode.json (beats picked from the transcript) + activity.json (cutaway pen-activity rule).
usage: sab_edl.py <slug>"""
import json, os, sys, re, numpy as np
slug=sys.argv[1]; SSD=os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')); E=f'{SSD}/SAB-production/episodes/{slug}'; W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug)
cfg=json.load(open(W+'/episode.json')); B=cfg['beats']
act=np.array(json.load(open(W+'/activity.json'))); AT=dict((int(i),v) for i,v in act)
def activity(a,b): return np.mean([AT.get(i,0) for i in range(int(a),int(b)+1)])
d0,d1=B['draw'] if 'draw' in B else (0,0); med=np.median([AT.get(i,0) for i in range(int(d0),int(d1))]) if d1-d0>=1 else 0.1
# cutaways: candidates listed in config are re-checked against the rules
INSTR=re.compile(r"draw|drawing|connect|curve|line|circle|colou?r|like that|leg|arm|frosting|sprinkles?|eyes?|mouth|smile|shoe|feet|foot|top|bottom|side|around|start|then|now i'?m|we'?re gonna|let'?s")
cuts=[]; last=-1e9
for c in cfg.get('cutaways',[]):
    a,b=c['a'],min(c['b'],c['a']+6)
    why=[]
    if INSTR.search(c['text'].lower()): why.append('instruction words')
    if activity(a,b)>1.3*med: why.append('pen busy %.3f>%.3f'%(activity(a,b),1.3*med))
    if c.get('reviewed'): why=[w+' (overridden: frames reviewed)' for w in why]; print('  ',why); why=[]
    if a-last<35: why.append('too close')
    if any(z['t_in']-1<a<z['t_out']+1 or z['t_in']-1<b<z['t_out']+1 for z in cfg.get('zooms',[])): why.append('inside zoom')
    print('cutaway',a,b,'REJECT '+', '.join(why) if why else 'ok'); 
    if not why: cuts.append((a,b)); last=b
S=[]; n={}
def add(role,cam,a,b,**k):
    n[role]=n.get(role,0)+1; S.append(dict(name=f"{role}{n[role]-1}" if role not in ('intro','wipe','iris','outro','review','bye') else role,role=role,cam=cam,a=round(a,3),b=round(b,3),**k))
if 'intro' in B:
    add('intro','front',*B['intro'])
    add('wipe','wipe',B['intro'][1],B['intro'][1]+0.8,top_a=d0-0.8)
# drawing block: top cam (chunked ≤25 s for render budget), skips removed, cutaways to front
pieces=[(d0,d1)]
for sa,sb in cfg.get('skips',[])+cuts:
    out=[]
    for x,y in pieces:
        if sb<=x or sa>=y: out.append((x,y))
        else:
            if sa>x: out.append((x,sa))
            if sb<y: out.append((sb,y))
    pieces=out
evts=sorted([(x,y,'draw') for x,y in pieces]+[(a,b,'cut') for a,b in cuts])
for x,y,k in evts:
    if k=='cut': add('cutaway','front',x,y); continue
    if y-x<0.5: continue
    m=max(1,int(np.ceil((y-x)/25))); st=(y-x)/m
    for i in range(m): add('draw','top',x+i*st,x+(i+1)*st)
for role,cam,k in [('to_color','front','color_ask'),('to_color','top','color_pick'),('to_color','front','color_go')]:
    if k in B: add(role,cam,*B[k])
c0,c1=B['montage'] if 'montage' in B else (0,0); sp=cfg.get('montage_speed',10); x=c0; k=0
while x<c1-1:
    y=min(x+50,c1); y=c1 if c1-y<20 else y
    add('montage','front' if k%3==2 else 'top',x,y,speed=sp); x=y; k+=1
if 'review' in B: add('review','review',*B['review'])
if 'bye' in B: add('bye','front',*B['bye']); add('iris','iris',B['bye'][1],B['bye'][1]+1.0)
oz=float(os.popen(f"ffprobe -v error -show_entries format=duration -of csv=p=0 '{E}/outro_anim_v.mp4'").read() or 13)
if 'bye' in B: add('outro_video','outro',0,oz-1.0)
it=cfg.get('intro',{}); edl=dict(slug=slug,out_k=cfg.get('out_k',2),header=cfg.get('header','video-how-to-draw-a.png'),faces=cfg['faces'],zooms=cfg.get('zooms',[]),frame_margin=cfg.get('frame_margin',0.035),
    title=it.get('title'),intro_shots=it.get('shots'),music=cfg['music'],segments=S)
json.dump(edl,open(W+'/edl.json','w'),indent=1)
dur=sum((s['b']-s['a'])/s.get('speed',1) for s in S); print(len(S),'segments, %d:%02d'%(dur//60,dur%60))
