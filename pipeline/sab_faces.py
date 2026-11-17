"""Face-safe punch-in framing, shared by the intro and the wipe (so the wipe starts on the intro's last frame).
head_boxes (edl): for each person, the box their head occupies at any time during the intro (normalised source
coords, from tools/head_boxes.py). A punch-in keeps the punched-in person's head box fully inside (top included);
every other head box is either fully inside or fully outside, so no frame edge ever slices a head; any head
kept in frame is kept vertically too (the whole head box, give or take its bottom margin). Zooms out when nothing fits."""
import numpy as np

def face_safe(z,cx,cy,boxes):
    if z<1.1 or not boxes: return z,cx,cy
    B=list(boxes.values()) if isinstance(boxes,dict) else boxes
    tgt=min(B,key=lambda b:abs((b[0]+b[2])/2-cx)); others=[b for b in B if b is not tgt]
    while z>1.0:
        w=1/z; want=cx-w/2; best=None
        for x0 in np.arange(0,1-w+1e-9,0.002):
            if not (x0<=tgt[0] and x0+w>=tgt[2]): continue
            inside=[tgt]; ok=True
            for b in others:
                if x0<=b[0] and x0+w>=b[2]: inside.append(b)
                elif not (x0>=b[2] or x0+w<=b[0]): ok=False; break
            if not ok: continue
            lo=max(max(0,b[3]-0.04-w) for b in inside); hi=min(min(1-w,b[1]) for b in inside)   # every head in frame: the whole head box
            if lo>hi+1e-9: continue
            y0=min(max(cy-w/2,lo),hi)
            if best is None or abs(x0-want)<abs(best[0]-want): best=(x0,y0)
        if best is not None: return z,best[0]+w/2,best[1]+w/2
        z-=0.05
    return 1.0,0.5,0.5
