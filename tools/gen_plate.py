"""Generate a clean thumbnail base plate (no text/logo/banner) from the Look C wood plate as reference.
usage: gen_plate.py [n]  -> cache/plates/wood-clean_<i>.png"""
import os, sys, base64
ROOT=os.path.join(os.path.expanduser(os.environ.get('SAB_SSD','~/sab-data')),'SAB-production'); sys.path.insert(0,ROOT+'/tools')
from gen_lettering import edit
P=("Recreate this scene as a clean, empty background plate for a YouTube thumbnail. Top-down photo of the same warm light oak table "
   "with the same black art markers with colored caps lying around the outer edges (left and right sides and top corners), fully intact, "
   "none cut off or clipped. Two blank white sheets of drawing paper side by side in the middle, slightly rotated like the reference, "
   "completely blank. Remove ALL text, the logo, and the blue banner: the top area is plain wood. Keep the top 18% and bottom 22% of the "
   "image clear of markers so titles can be placed there. Soft natural daylight, gentle shadows, photographic, no people, no hands, no words.")
n=int(sys.argv[1]) if len(sys.argv)>1 else 2; os.makedirs(ROOT+'/cache/plates',exist_ok=True)
r=edit('gpt-image-2.6-sunburst',P,[ROOT+'/assets/look-c/thumbnail-blue-how-to-draw.png'],n=n,size='1536x1024',background='opaque',quality='high')
for i,d in enumerate(r['data']):
    open(f"{ROOT}/cache/plates/wood-clean_{i}.png",'wb').write(base64.b64decode(d['b64_json'])); print('saved',i)
