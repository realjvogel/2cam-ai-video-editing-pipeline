exec(open('ov.py').read().split("tag('t_raw'")[0])   # helpers only
VW,VH=1080,1350
def paperv():
    im=Image.new('RGBA',(VW,VH),(250,246,236,255)); d=ImageDraw.Draw(im)
    for x in range(0,VW,36): d.line((x,0,x,VH),fill=(222,226,228,255),width=1)
    for y in range(0,VH,36): d.line((0,y,VW,y),fill=(222,226,228,255),width=1)
    return im
def sticker(txt,sz,angle,seed):
    f=MK(sz); w=int(f.getlength(txt))+60; h=int(sz*1.6)
    st=Image.new('RGBA',(w+24,h+24),(0,0,0,0)); sd=ImageDraw.Draw(st)
    wobbly_rect(sd,(12,12,w+8,h+8),COL['claude']+(255,),COL['claude']+(255,),3,seed,r=16)
    wobbly_rect(sd,(4,4,w,h),(255,254,249,255),INK,4,seed+1,r=16)
    sd.text((30,(h-sz*1.25)/2),txt,font=f,fill=INK)
    return st.rotate(angle,resample=Image.BICUBIC,expand=True)
def header(im):
    d=ImageDraw.Draw(im)
    t='AI editing flow'; f=MK(82); x=(VW-f.getlength(t))/2-40
    hl(d,d.textbbox((x,46),t,font=f)); d.text((x,46),t,font=f,fill=INK)
    t2='for Super Art Bros'; f2=MK(40); d.text(((VW-f2.getlength(t2))/2-40,150),t2,font=f2,fill=(74,71,64,255))
    st=sticker('take 1',34,-9,51); im.alpha_composite(st,(VW-st.width-34,128))
VY=250; VWID=1040; VHT=585
def mainbg():
    im=paperv(); header(im); d=ImageDraw.Draw(im)
    wobbly_rect(d,(20-9,VY-9,20+VWID+9,VY+VHT+9),INK,INK,3,61,r=12)
    im.convert('RGB').save('ov/v_main.png')
RW,RH=840,473; RY1,RY2=262,800
def rawbg():
    im=paperv(); header(im); d=ImageDraw.Draw(im)
    for i,y in enumerate((RY1,RY2)):
        wobbly_rect(d,(120-8,y-8,120+RW+8,y+RH+8),INK,INK,3,70+i,r=10)
    im.convert('RGB').save('ov/v_raw.png')
def rawlabels():
    can=Image.new('RGBA',(VW,VH),(0,0,0,0)); d=ImageDraw.Draw(can)
    for y,lab in ((RY1,'iPad · front'),(RY2,'iPhone · overhead')):
        f=KB(30); w=f.getlength(lab)+30
        d.rounded_rectangle((132,y+12,132+w,y+58),radius=10,fill=(255,254,249,235),outline=INK,width=2)
        d.text((147,y+14),lab,font=f,fill=INK)
    can.save('ov/v_rawlab.png')
def calloutv(name,title,sub,who,angle,seed,dim=False,cy=1095):
    can=Image.new('RGBA',(VW,VH),(0,0,0,110 if dim else 0))
    t=MK(58); s=KB(32)
    words=title.split(); lines=[]; cur=''
    for w_ in words:
        tr=(cur+' '+w_).strip()
        if t.getlength(tr)>960 and cur: lines.append(cur); cur=w_
        else: cur=tr
    lines.append(cur)
    tw=max(max(t.getlength(l) for l in lines), s.getlength(sub)+50)+90
    th=len(lines)*78+96
    im=Image.new('RGBA',(int(tw)+44,int(th)+44),(0,0,0,0)); d=ImageDraw.Draw(im)
    wobbly_rect(d,(16,16,tw+10,th+10),COL[who]+(255,),COL[who]+(255,),3,seed,r=24)
    wobbly_rect(d,(6,6,tw,th),(255,254,249,255),INK,5,seed+7,r=24)
    y=28
    for l in lines: d.text(((tw-t.getlength(l))/2+3,y),l,font=t,fill=INK); y+=78
    sw=s.getlength(sub)+40; x=(tw-sw)/2+3
    d.ellipse((x,y+20,x+24,y+44),fill=COL[who]+(255,),outline=INK,width=3)
    d.text((x+38,y+4),sub,font=s,fill=(74,71,64,255))
    im=im.rotate(angle,resample=Image.BICUBIC,expand=True)
    can.alpha_composite(im,((VW-im.width)//2,int(cy-im.height/2)))
    can.save(f'ov/{name}.png')
calloutv('vk_raw','Transcribe + sync separate video files for alignment','Whisper + audio waveform match','tools',-1.5,11,dim=True,cy=780)
calloutv('vk_punch','Auto punch-ins','Claude picks the moment','claude',1.3,12)
calloutv('vk_title','AI title art, behind the people','OpenAI lettering + RVM cut-out','openai',-1.2,13)
calloutv('vk_zoom','Auto-detect and add zoom + pan','Claude plans it, ffmpeg renders it','claude',1.2,14)
calloutv('vk_cut','Auto cutaways on questions','Claude reads the transcript','claude',-1.3,15)
calloutv('vk_montage','Speed-up coloring montage','ffmpeg, 10x with music','tools',1.4,16)
calloutv('vk_review','Auto review layout','both drawings + face card','claude',-1.1,17)
calloutv('vk_outro','Outro with their real drawings','Claude + ffmpeg','claude',1.2,18)
def cardv(name,lines,stick=False):
    im=paperv(); top=Image.new('RGBA',(VW,VH),(0,0,0,0)); d=ImageDraw.Draw(top)
    for (txt,font,y,col,hi) in lines:
        x=(VW-font.getlength(txt))/2
        if hi: hl(ImageDraw.Draw(im),d.textbbox((x,y),txt,font=font))
        d.text((x,y),txt,font=font,fill=col)
    im.alpha_composite(top)
    if stick:
        st=sticker('take 1',60,-8,31); im.alpha_composite(st,(VW-st.width-150,880))
    im.convert('RGB').save(f'ov/{name}.png')
cardv('v_open',[('AI editing',MK(130),430,INK,True),('flow',MK(130),580,INK,True),('for Super Art Bros',MK(62),760,INK,False)],stick=True)
cardv('v_end',[('27 min of raw footage',KB(56),430,INK,False),('a finished',MK(96),520,INK,True),('episode',MK(96),640,INK,True),
               ('edited by our AI flow,',KB(46),800,(74,71,64,255),False),('while we just draw',KB(46),860,(74,71,64,255),False),('SUPER ART BROS',MK(36),1040,(106,100,88,255),False)])
mainbg(); rawbg(); rawlabels(); print('ok')
