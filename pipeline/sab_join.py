"""Join an episode recorded in two parts (each prepped and rendered as its own slug) into one work dir,
ready for `sab_render.py <out> assemble` and `finalize`.
usage: sab_join.py <out_slug> <part_a_slug> <part_b_slug>
Part A gives the opening and lesson (intro, wipe, draw, cutaway); part B gives everything from "to color" on.
Part B's times are shifted by part A's audio length so one joined dialogue track (dlg48.wav) serves both."""
import os, sys, json, wave, shutil
WR=os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps'))
out,pa,pb=sys.argv[1:4]; W=f'{WR}/{out}'; A,B=f'{WR}/{pa}',f'{WR}/{pb}'; os.makedirs(W+'/vo',exist_ok=True)
ea,eb=json.load(open(A+'/edl.json')),json.load(open(B+'/edl.json'))
def wlen(p): w=wave.open(p); return w.getnframes()/w.getframerate()
LA=wlen(A+'/dlg48.wav')
segs=[]
for part,e,shift,roles in (('a',ea,0.0,('intro','wipe','draw','cutaway')),('b',eb,LA,None)):
    for s in e['segments']:
        if (roles and s['role'] not in roles) or (not roles and s['role'] in ('intro','wipe','draw','cutaway')): continue
        s=dict(s); src=f"{A if part=='a' else B}/vo/{s['name']}.mp4"
        s['name']=s['name'] if s['role']=='iris' else f"{part}_{s['name']}"      # assemble looks up 'iris' by name
        if s['role'] not in ('outro_video',): s['a']=round(s['a']+shift,3); s['b']=round(s['b']+shift,3)
        if 'keep' in s: s['keep']=[[x+shift,y+shift] for x,y in s['keep']]
        dst=f"{W}/vo/{s['name']}.mp4"
        if os.path.lexists(dst): os.remove(dst)
        os.symlink(src,dst); segs.append(s)
edl=dict(ea); edl['music']=eb['music']; edl['segments']=segs; edl['slug']=out; edl['parts']=[pa,pb,LA]
json.dump(edl,open(W+'/edl.json','w'),indent=1)
# joined dialogue: A then B (same sample rate and layout)
wa,wb=wave.open(A+'/dlg48.wav'),wave.open(B+'/dlg48.wav'); o=wave.open(W+'/dlg48.wav.tmp','wb'); o.setparams(wa.getparams())
for w in (wa,wb):
    while True:
        d=w.readframes(1<<20)
        if not d: break
        o.writeframes(d)
o.close(); os.replace(W+'/dlg48.wav.tmp',W+'/dlg48.wav')
for f in ('prep.json','papers.json','music48.wav'): shutil.copy(A+'/'+f if f!='music48.wav' else B+'/'+f, W+'/'+f)
missing=[s['name'] for s in segs if not os.path.exists(f"{W}/vo/{s['name']}.mp4")]
print('joined',len(segs),'segments; part A audio %.1f s; missing renders:'%LA, missing)
