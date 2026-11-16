"""Generate a subject word in the Look C lettering style via OpenAI image edits (transparent PNG candidates)."""
import sys, os, re, json, base64, uuid, urllib.request, time
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def key():
    if os.environ.get('OPENAI_API_KEY'): return os.environ['OPENAI_API_KEY']
    t=open(os.path.join(ROOT,'secrets.env')).read(); return re.search(r'OPENAI_API_KEY\s*=\s*(\S+)',t).group(1).strip('"\'')
def edit(model,prompt,images,n=2,size='1536x1024',background='transparent',quality='high'):
    b='----sab'+uuid.uuid4().hex; parts=[]
    def field(k,v): parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    for k,v in dict(model=model,prompt=prompt,n=n,size=size,background=background,quality=quality,output_format='png').items(): field(k,v)
    for p in images:
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="image[]"; filename="{os.path.basename(p)}"\r\nContent-Type: image/png\r\n\r\n'.encode()+open(p,'rb').read()+b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    req=urllib.request.Request('https://api.openai.com/v1/images/edits',data=b''.join(parts),headers={'Authorization':'Bearer '+key(),'Content-Type':'multipart/form-data; boundary='+b})
    return json.load(urllib.request.urlopen(req,timeout=300))
if __name__=='__main__':
    word=sys.argv[1].upper(); model=sys.argv[2] if len(sys.argv)>2 else 'gpt-image-1.5'
    ref=os.path.join(ROOT,'assets/look-c/video-how-to-draw-a.png')
    prompt=(f'Render the single word "{word}" exactly as spelled. Match the attached reference\'s bold italic 1930s soft-serif lettering, '
            'warm cream fill, deep plum outline and subtle plum drop shadow, same slight upward tilt and hand-lettered texture. '
            'Keep the word on a single line with legible spacing and clear margins. Output only this word on a transparent background. '
            'Omit extra punctuation, headlines, logo, props, and underline.')
    t0=time.time()
    try: r=edit(model,prompt,[ref])
    except urllib.error.HTTPError as e: print('HTTP',e.code,e.read()[:400].decode(errors='replace')); sys.exit(1)
    out=os.path.join(ROOT,'cache/lettering'); os.makedirs(out,exist_ok=True)
    for i,d in enumerate(r['data']):
        p=os.path.join(out,f'{word.lower()}_{model}_{i}.png'); open(p,'wb').write(base64.b64decode(d['b64_json'])); print('saved',p)
    print('secs',round(time.time()-t0),'usage',r.get('usage',{}).get('total_tokens'))
