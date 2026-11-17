"""List lesson segments whose virtual camera differs between two edit plans (so only those get re-rendered).
usage: sab_changed.py <slug> <old_edl.json> [--delete]   (compares with W/edl.json; --delete removes their renders)"""
import os, sys, json, numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from sab_cams import Cams
slug,old=sys.argv[1],sys.argv[2]; W=os.path.join(os.path.expanduser(os.environ.get('SAB_WORK','~/sab/eps')),slug)
A,B=json.load(open(old)),json.load(open(W+'/edl.json')); CA,CB=Cams(W,A),Cams(W,B)
olds={(s['name'],s['a'],s['b']) for s in A['segments']}; out=[]
for s in B['segments']:
    if s['cam']!='top' or s['role']=='montage': continue
    if (s['name'],s['a'],s['b']) not in olds: out.append(s['name']); continue
    if any(np.abs(np.array(CA.cam(t))-np.array(CB.cam(t))).max()>1e-3 for t in np.arange(s['a'],s['b'],0.25)): out.append(s['name'])
print(' '.join(out))
if '--delete' in sys.argv:
    for n in out:
        p=f"{W}/vo/{n}.mp4"
        if os.path.exists(p): os.remove(p)
