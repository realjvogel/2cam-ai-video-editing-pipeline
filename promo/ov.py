from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random, math
F='/'.join(__file__.split('/')[:-1])+'/fonts/'
MK=lambda s: ImageFont.truetype(F+'PermanentMarker-Regular.ttf',s)
KB=lambda s: ImageFont.truetype(F+'Kalam-Bold.ttf',s)
KR=lambda s: ImageFont.truetype(F+'Kalam-Regular.ttf',s)
INK=(42,42,42,255)
COL={'me':(242,194,0),'claude':(217,119,87),'openai':(63,165,110),'tools':(94,159,216)}
W,H=1920,1080
def wobbly_rect(d,box,fill,outline,width,seed,r=18):
    random.seed(seed)
    x0,y0,x1,y1=box; pts=[]
    def edge(a,b,n=14):
        for i in range(n):
            t=i/n; pts.append((a[0]+(b[0]-a[0])*t+random.uniform(-1.6,1.6),a[1]+(b[1]-a[1])*t+random.uniform(-1.6,1.6)))
    c=[(x0+r,y0),(x1-r,y0),(x1,y0+r),(x1,y1-r),(x1-r,y1),(x0+r,y1),(x0,y1-r),(x0,y0+r)]
    for i in range(0,8,2):
        edge(c[i],c[i+1])
        # corner arc
        cx=[x1-r,x1-r,x0+r,x0+r][i//2]; cy=[y0+r,y1-r,y1-r,y0+r][i//2]
        a0=[-90,0,90,180][i//2]
        for k in range(6): a=math.radians(a0+15*k); pts.append((cx+r*math.cos(a),cy+r*math.sin(a)))
    d.polygon(pts,fill=fill)
    d.line(pts+[pts[0]],fill=outline,width=width,joint='curve')
def tag(name,title,sub,who,angle=-1.5,seed=1):
    t=MK(46); s=KB(29)
    tw=max(t.getlength(title), s.getlength(sub)+44)+70
    th=150
    im=Image.new('RGBA',(int(tw)+40,th+40),(0,0,0,0)); d=ImageDraw.Draw(im)
    wobbly_rect(d,(14,14,tw+8,th+8),COL[who]+(255,),COL[who]+(255,),3,seed)   # shadow
    wobbly_rect(d,(6,6,tw,th),(255,254,249,255),INK,4,seed+7)
    d.text((34,18),title,font=t,fill=INK)
    d.ellipse((34,103,56,125),fill=COL[who]+(255,),outline=INK,width=2)
    d.text((68,92),sub,font=s,fill=(74,71,64,255))
    im=im.rotate(angle,resample=Image.BICUBIC,expand=True)
    can=Image.new('RGBA',(W,H),(0,0,0,0)); can.alpha_composite(im,(56,H-im.height-48))
    can.save(f'ov/{name}.png')
def paper():
    im=Image.new('RGBA',(W,H),(250,246,236,255)); d=ImageDraw.Draw(im)
    for x in range(0,W,36): d.line((x,0,x,H),fill=(222,226,228,255),width=1)
    for y in range(0,H,36): d.line((0,y,W,y),fill=(222,226,228,255),width=1)
    return im
def hl(d,box):
    x0,y0,x1,y1=box; d.rectangle((x0-6,y0+(y1-y0)*0.55,x1+6,y1-(y1-y0)*0.06),fill=(255,214,51,200))
def card(name,lines):
    im=paper(); top=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(top)
    for (txt,font,y,col,hi) in lines:
        w=font.getlength(txt); x=(W-w)/2
        if hi:
            bb=d.textbbox((x,y),txt,font=font); hl(ImageDraw.Draw(im),bb)
        d.text((x,y),txt,font=font,fill=col)
    im.alpha_composite(top); im.convert('RGB').save(f'ov/{name}.png')
# raw split background
def rawbg():
    im=paper(); d=ImageDraw.Draw(im)
    for i,(x,lab,who) in enumerate([(60,'iPad · front','me'),(980,'iPhone · overhead','me')]):
        wobbly_rect(d,(x-10,250-10,x+880+10,250+495+10),INK,INK,3,40+i,r=10)
        d.text((x+440-KB(34).getlength(lab)/2,190),lab,font=KB(34),fill=INK)
    d.text((W/2-MK(54).getlength('The raw footage')/2,70),'The raw footage',font=MK(54),fill=INK)
    im.convert('RGB').save('ov/rawbg.png')
tag('t_raw','27 min of raw footage','synced by audio waveform, transcribed by Whisper','tools',-1.2,1)
tag('t_punch','Punch-in','Claude picks the moment','claude',1.2,2)
tag('t_title','Title art','OpenAI lettering + RVM cut-out','openai',-1.5,3)
tag('t_zoom','Detail zoom','Claude plans it, ffmpeg renders it','claude',1.0,4)
tag('t_cut','Cutaway','Claude finds the question','claude',-1.0,5)
tag('t_montage','Coloring at 10x','ffmpeg','tools',1.4,6)
tag('t_review','Review layout','Claude frames it','claude',-1.3,7)
tag('t_outro','Outro with their real drawings','Claude + ffmpeg','claude',1.1,8)
card('c_end2',[('27 min of raw footage',KB(60),310,INK,False),
              ('a finished episode',MK(96),395,INK,True),
              ('edited by our AI flow, while we just draw',KB(46),560,(74,71,64,255),False),
              ('SUPER ART BROS',MK(36),720,(106,100,88,255),False)])
def rawbg2():
    im=paper(); d=ImageDraw.Draw(im)
    for i,(x,lab) in enumerate([(60,'iPad · front'),(980,'iPhone · overhead')]):
        wobbly_rect(d,(x-10,250-10,x+880+10,250+495+10),INK,INK,3,40+i,r=10)
        d.text((x+440-KB(34).getlength(lab)/2,190),lab,font=KB(34),fill=INK)
    t='Our AI editing flow'; f=MK(64); x=W/2-f.getlength(t)/2
    hl(d,d.textbbox((x,60),t,font=f)); d.text((x,60),t,font=f,fill=INK)
    im.convert('RGB').save('ov/rawbg2.png')
rawbg2()
print('ok')

def callout(name,title,sub,who,angle,seed):
    can=Image.new('RGBA',(W,H),(0,0,0,95)); 
    t=MK(78); s=KB(38)
    # wrap title to max 1400px
    words=title.split(); lines=[]; cur=''
    for w_ in words:
        tr=(cur+' '+w_).strip()
        if t.getlength(tr)>1400 and cur: lines.append(cur); cur=w_
        else: cur=tr
    lines.append(cur)
    tw=max(max(t.getlength(l) for l in lines), s.getlength(sub)+56)+120
    th=len(lines)*96+110
    im=Image.new('RGBA',(int(tw)+50,int(th)+50),(0,0,0,0)); d=ImageDraw.Draw(im)
    wobbly_rect(d,(18,18,tw+10,th+10),COL[who]+(255,),COL[who]+(255,),3,seed,r=26)
    wobbly_rect(d,(6,6,tw,th),(255,254,249,255),INK,5,seed+7,r=26)
    y=34
    for l in lines:
        d.text(((tw-t.getlength(l))/2+3,y),l,font=t,fill=INK); y+=96
    sw=s.getlength(sub)+44; x=(tw-sw)/2+3
    d.ellipse((x,y+22,x+28,y+50),fill=COL[who]+(255,),outline=INK,width=3)
    d.text((x+44,y+6),sub,font=s,fill=(74,71,64,255))
    im=im.rotate(angle,resample=Image.BICUBIC,expand=True)
    can.alpha_composite(im,((W-im.width)//2,(H-im.height)//2))
    can.save(f'ov/{name}.png')
callout('k_raw','Transcribe + sync separate video files for alignment','Whisper + audio waveform match','tools',-1.5,11)
callout('k_punch','Auto punch-ins','Claude picks the moment','claude',1.3,12)
callout('k_title','AI title art, behind the people','OpenAI lettering + RVM cut-out','openai',-1.2,13)
callout('k_zoom','Auto-detect and add zoom + pan','Claude plans it, ffmpeg renders it','claude',1.2,14)
callout('k_cut','Auto cutaways on questions','Claude reads the transcript','claude',-1.3,15)
callout('k_montage','Speed-up coloring montage','ffmpeg, 10x with music','tools',1.4,16)
callout('k_review','Auto review layout','both drawings + face card','claude',-1.1,17)
callout('k_outro','Outro with their real drawings','Claude + ffmpeg','claude',1.2,18)
def opencard():
    im=paper(); d=ImageDraw.Draw(im)
    t='AI editing flow'; f=MK(140); x=W/2-f.getlength(t)/2
    hl(d,d.textbbox((x,330),t,font=f)); d.text((x,330),t,font=f,fill=INK)
    t2='for Super Art Bros'; f2=MK(76); d.text((W/2-f2.getlength(t2)/2,530),t2,font=f2,fill=INK)
    # sticker "take 1"
    st=Image.new('RGBA',(330,150),(0,0,0,0)); sd=ImageDraw.Draw(st)
    wobbly_rect(sd,(16,16,320,140),COL['claude']+(255,),COL['claude']+(255,),3,31,r=20)
    wobbly_rect(sd,(6,6,310,130),(255,254,249,255),INK,5,32,r=20)
    sd.text((158-MK(64).getlength('take 1')/2,22),'take 1',font=MK(64),fill=INK)
    st=st.rotate(-8,resample=Image.BICUBIC,expand=True); im.alpha_composite(st,(1380,640))
    im.convert('RGB').save('ov/c_open3.png')
def rawbg3():
    im=paper(); d=ImageDraw.Draw(im)
    for i,(x,lab) in enumerate([(60,'iPad · front'),(980,'iPhone · overhead')]):
        wobbly_rect(d,(x-10,292-10,x+880+10,292+495+10),INK,INK,3,40+i,r=10)
        d.text((x+440-KB(38).getlength(lab)/2,226),lab,font=KB(38),fill=INK)
    im.convert('RGB').save('ov/rawbg3.png')
opencard(); rawbg3()
