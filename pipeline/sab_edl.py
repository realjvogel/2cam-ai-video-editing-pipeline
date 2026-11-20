"""Build edl.json from episode.json (beats picked from the transcript) + activity.json (cutaway pen-activity rule).
usage: sab_edl.py <slug>"""
import json, os, sys, re, numpy as np
slug=sys.argv[1]; SSD=os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')); E=f'{SSD}/SAB-production/episodes/{slug}'; W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug)
cfg=json.load(open(W+'/episode.json')); B=dict(cfg['beats'])
# intro / review / bye may be a list of ranges (to cut a fumble or a retake out of the middle)
RANGES={k:(v if isinstance(v[0],list) else [v]) for k,v in B.items() if k in ('intro','review','bye')}
for k,v in RANGES.items(): B[k]=[v[0][0],v[-1][1]]
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
    n[role]=n.get(role,0)+1; one=role in ('intro','wipe','iris','outro','review','bye') and n[role]==1
    S.append(dict(name=role if one else f"{role}{n[role]-1}",role=role,cam=cam,a=round(a,3),b=round(b,3),**k))
if 'intro' in B:
    add('intro','front',*B['intro'],**({'keep':RANGES['intro']} if len(RANGES['intro'])>1 else {}))
    add('wipe','wipe',B['intro'][1],B['intro'][1]+0.8,top_a=d0-0.8)
# drawing block: top cam (chunked ≤25 s, ≤10 s at 4K, so one chunk fits a render pass), skips removed, cutaways to front
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
    CH=10 if cfg.get('out_k',2)==2 else 25; m=max(1,int(np.ceil((y-x)/CH))); st=(y-x)/m
    for i in range(m): add('draw','top',x+i*st,x+(i+1)*st)
for role,cam,k in [('to_color','front','color_ask'),('to_color','top','color_pick'),('to_color','front','color_go')]:
    if k in B: add(role,cam,*B[k])
c0,c1=B['montage'] if 'montage' in B else (0,0); sp=cfg.get('montage_speed',10); x=c0; k=0
while x<c1-1:
    y=min(x+50,c1); y=c1 if c1-y<20 else y
    add('montage','front' if k%3==2 else 'top',x,y,speed=sp); x=y; k+=1
for x in cfg.get('extra',[]):   # optional extra beats after the montage, in order: {role: to_color|draw|montage, cam, a, b}
    if x['role']=='draw':
        CH=10 if cfg.get('out_k',2)==2 else 25; m=max(1,int(np.ceil((x['b']-x['a'])/CH))); st=(x['b']-x['a'])/m
        for i in range(m): add('draw','top',x['a']+i*st,x['a']+(i+1)*st)
    elif x['role']=='montage':
        u=x['a']
        while u<x['b']-1:
            y=min(u+50,x['b']); y=x['b'] if x['b']-y<20 else y
            add('montage','front' if k%3==2 else 'top',u,y,speed=sp); u=y; k+=1
    else: add(x['role'],x.get('cam','front'),x['a'],x['b'])
for r in RANGES.get('review',[]): add('review','review',*r)
for r in RANGES.get('bye',[]): add('bye','front',*r)
if 'bye' in B: add('iris','iris',B['bye'][1],B['bye'][1]+1.0)
oz=float(os.popen(f"ffprobe -v error -show_entries format=duration -of csv=p=0 '{E}/outro_anim_v.mp4'").read() or 13)
if 'bye' in B: add('outro_video','outro',0,oz-1.0)
# snap hard cuts (where the dialogue jumps) to the nearest quiet 30 ms so a word is never clipped:
# a segment end may move up to 0.6 s later (finish the word) or 0.15 s earlier; a start up to 0.6 s earlier or 0.15 s later.
try:
    import wave as _wv
    _w=_wv.open(W+'/dlg48.wav'); _sr=_w.getframerate(); _x=np.frombuffer(_w.readframes(_w.getnframes()),np.int16).reshape(-1,_w.getnchannels()).mean(1)
    def _e(t): s=_x[int(max(0,t-0.015)*_sr):int((t+0.015)*_sr)]; return float(np.sqrt((s**2).mean())) if len(s) else 0
    def _quiet(t,lo,hi):
        cand=np.arange(t+lo,t+hi+1e-6,0.01); en=np.array([_e(u) for u in cand]); best=en.min()
        ok=cand[en<=best*1.5+30]; return float(ok[np.argmin(np.abs(ok-t))])
    SPEECH=('draw','to_color','review','bye')
    for i in range(len(S)-1):
        A_,B_=S[i],S[i+1]
        if abs(A_['b']-B_['a'])<0.05: continue   # continuous: no cut
        if A_['role'] in SPEECH: nb=round(_quiet(A_['b'],-0.15,0.6),3); print('snap end  ',A_['name'],A_['b'],'->',nb); A_['b']=nb
        if B_['role'] in SPEECH and B_['role']!='draw': na=round(_quiet(B_['a'],-0.6,0.15),3); print('snap start',B_['name'],B_['a'],'->',na); B_['a']=na
    for j in range(len(S)-1):
        if S[j]['role']=='bye' and S[j+1]['role']=='iris': S[j+1]['a']=S[j]['b']; S[j+1]['b']=S[j]['b']+1.0
except FileNotFoundError: pass
# detail zooms: follow the adult's hand. Stay on the adult's paper while his hand is on it; glide to the
# kid's paper only when it stays off for the next 6 s; come back (starting 1 s early) when it returns for 2 s.
def side_schedule(z):
    """Adult-hand coverage above the sheet's own baseline (the ink already on it = running minimum over +-30 s).
    Hand counts as off below +0.035 and back on above +0.05."""
    if not os.path.exists(W+'/sides.json'): return None
    H=dict((int(r[0]),r[1] if z['first']=='L' else r[2]) for r in json.load(open(W+'/sides.json')))
    raw=lambda t: float(np.median([H.get(int(t)+k,H.get(int(t),0)) for k in (-1,0,1)]))
    lo,hi=int(z['t_in']),int(z['t_out'])
    def h(t): return raw(t)-min(raw(u) for u in range(max(lo,int(t)-30),min(hi,int(t)+30)+1))
    kid='R' if z['first']=='L' else 'L'; sched=[[z['t_in'],z['first']]]; cur=z['first']; last=z['t_in']
    t=z['t_in']+2
    while t<z['t_out']-4:
        if cur==z['first'] and t-last>=4 and all(h(t+k)<0.035 for k in range(6)): cur=kid; sched.append([t,cur]); last=t
        elif cur==kid and t-last>=6 and all(h(t+k)>0.05 for k in range(2)): cur=z['first']; sched.append([max(last+5,t-1),cur]); last=t
        t+=1
    return sched
zooms=[]
for z in cfg.get('zooms',[]):
    z=dict(z); sc=side_schedule(z)
    if sc: z['sides']=sc; print('zoom',z['t_in'],z['t_out'],'sides',sc)
    zooms.append(z)
it=cfg.get('intro',{}); edl=dict(slug=slug,out_k=cfg.get('out_k',2),header=cfg.get('header','video-how-to-draw-a.png'),faces=cfg['faces'],head_boxes=cfg.get('head_boxes'),duck=cfg.get('duck',[]),zooms=zooms,frame_margin=cfg.get('frame_margin',0.035),base_zoom_max=cfg.get('base_zoom_max',9),zoom_max=cfg.get('zoom_max',2.0),
    title=it.get('title'),intro_shots=it.get('shots'),music=cfg['music'],segments=S)
json.dump(edl,open(W+'/edl.json','w'),indent=1)
dur=sum((s['b']-s['a'])/s.get('speed',1) for s in S); print(len(S),'segments, %d:%02d'%(dur//60,dur%60))
