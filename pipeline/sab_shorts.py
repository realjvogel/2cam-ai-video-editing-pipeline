"""YouTube Shorts (1080x1920, made for kids) from an episode's raw footage.
usage:
  sab_shorts.py <slug> timelapse                       both papers sped up, cutting adult <-> kid every 3 s (SAB_SHORT_SWAP), small wordmark,
                                                       opens on the finished drawings + title (2 s), ends on "Draw with us today!" + both drawings. SAB_SHORT_BG=blue|yellow, SAB_SHORT_MUSIC=<file>
  sab_shorts.py <slug> facts                           same, faster (SAB_SHORT_SPEED, default 1.4), with a fun-fact voiceover from W/shorts/facts.txt (TTS)
                                                       or Josh's own recording at W/shorts/vo.wav
  sab_shorts.py <slug> moment <raw_a> <raw_b> <captions.json> [name]
        opens on the finished drawings + title, then the front camera tight on the kid with big captions, then the end card. captions.json: [[raw_t0, raw_t1, "TEXT"], ...]
Output: W/shorts/<slug>-<kind>.mp4 (and copied to SAB - auto edits/Shorts/ by the caller)."""
import os, sys, json, subprocess, numpy as np
from PIL import Image, ImageFilter, ImageEnhance
slug, kind = sys.argv[1], sys.argv[2]
SSD = os.path.expanduser(os.environ.get('SAB_SSD', '~/sab-data')); R = SSD + '/SAB-production'; E = f'{R}/episodes/{slug}'
W = os.path.join(os.path.expanduser(os.environ.get('SAB_WORK', '~/sab/eps')), slug); O = W + '/shorts'; os.makedirs(O, exist_ok=True)
prep = json.load(open(W + '/prep.json')); edl = json.load(open(W + '/edl.json')); cfg = json.load(open(W + '/episode.json'))
FONTS = R + '/promo/fonts'; A = R + '/assets/look-c'
EA = f"{R}/episodes/{os.environ.get('SAB_SHORT_ART_SLUG', slug)}"   # finished drawings (split episodes: the part with the coloring)
CSLUG = os.environ.get('SAB_SHORT_COLOR_SLUG', slug)                    # coloring from another recording of the same episode
def run(a): subprocess.run(['ffmpeg', '-nostdin', '-v', 'error'] + a, check=True)
def raw(p):
    if os.path.exists(p): return p
    return SSD + p.split('data drive', 1)[1]
VW, VH = 1080, 1920
SW, SH = prep.get('src_w', 3840), prep.get('src_h', 2160)   # source frame size (Jan 2024 episodes are 1080p)

def background(path, style='blue'):
    """bright sunburst (blue or yellow, rotate between episodes) filling 9:16, small wordmark on top"""
    import math
    from PIL import ImageDraw
    c1, c2 = {'blue': ((58, 120, 200), (78, 142, 222)), 'yellow': ((236, 178, 52), (246, 198, 82))}[style]
    bg = Image.new('RGB', (VW, VH), c1); d = ImageDraw.Draw(bg); cx, cy, Rr, n = VW / 2, VH * .42, 3000, 24
    for i in range(0, n, 2):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d.polygon([(cx, cy), (cx + Rr * math.cos(a0), cy + Rr * math.sin(a0)), (cx + Rr * math.cos(a1), cy + Rr * math.sin(a1))], fill=c2)
    v = Image.new('L', (VW, VH), 0); ImageDraw.Draw(v).ellipse((-500, -300, VW + 500, VH + 300), fill=255); v = v.filter(ImageFilter.GaussianBlur(200))
    bg = Image.composite(bg, Image.new('RGB', (VW, VH), tuple(int(c * .75) for c in c1)), v).convert('RGBA')
    wm = Image.open(A + '/super-art-bros-wordmark-light.png').convert('RGBA'); wm = wm.resize((230, int(wm.height * 230 / wm.width)), Image.LANCZOS)
    clean = bg.copy(); bg.alpha_composite(wm, (VW // 2 - 115, 26)); bg.save(path); bg.clean = clean; return bg, 26 + wm.height

def title_card(path, width=900):
    """'How to draw a' + subject, transparent, shown over the bottom of the paper for the first seconds"""
    hd = Image.open(A + '/' + edl.get('header', 'video-how-to-draw-a.png')).convert('RGBA'); hd = hd.resize((int(width * .85), int(hd.height * width * .85 / hd.width)), Image.LANCZOS)
    sb = Image.open(E + '/subject-aligned.png').convert('RGBA'); sb = sb.resize((width, int(sb.height * width / sb.width)), Image.LANCZOS)
    im = Image.new('RGBA', (width, hd.height + sb.height - 30)); im.alpha_composite(hd, ((width - hd.width) // 2, 0)); im.alpha_composite(sb, (0, hd.height - 30))
    im.save(path); return im.height

def trim(im):
    a = np.asarray(im)[..., 3]; ys, xs = np.where(a > 8); return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))

def art_card(bg, path, lettering, end=False):
    """Both finished drawings as tilted photo cards.
    opener: small wordmark, title lettering on top. end: big Super Art Bros wordmark on top, small 'Draw with us today!' at the bottom."""
    c = (bg.clean if end else bg).copy()
    def card(f, h, rot):
        im = Image.open(f).convert('RGB'); im = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
        b = Image.new('RGBA', (im.width + 24, im.height + 24), (255, 255, 255, 255)); b.paste(im, (12, 12)); return b.rotate(rot, expand=True, resample=Image.BICUBIC)
    def shadow(im, xy):
        s = Image.new('RGBA', c.size, (0, 0, 0, 0)); s.paste((0, 0, 0, 255), (xy[0], xy[1] + 10), Image.new('L', im.size, 110))
        c.alpha_composite(s.filter(ImageFilter.GaussianBlur(18))); c.alpha_composite(im, xy)
    t = trim(lettering)
    if end:
        wm = trim(Image.open(A + '/super-art-bros-wordmark-light.png').convert('RGBA')); wm = wm.resize((720, int(wm.height * 720 / wm.width)), Image.LANCZOS)
        c.alpha_composite(wm, ((VW - wm.width) // 2, 90)); y = 90 + wm.height + 50
        a, b = card(EA + '/drawing_0.png', 560, 3), card(EA + '/drawing_1.png', 560, -3); x = (VW - a.width - b.width + 30) // 2
        shadow(a, (x, y)); shadow(b, (x + a.width - 30, y + 30))
        t = t.resize((560, int(t.height * 560 / t.width)), Image.LANCZOS); c.alpha_composite(t, ((VW - t.width) // 2, min(y + b.height + 70, 1690 - t.height)))
    else:
        t = t.resize((900, int(t.height * 900 / t.width)), Image.LANCZOS); c.alpha_composite(t, ((VW - t.width) // 2, 170))
        a, b = card(EA + '/drawing_0.png', 610, 3), card(EA + '/drawing_1.png', 610, -3); x = (VW - a.width - b.width + 30) // 2; y = 170 + t.height + 70
        shadow(a, (x, y)); shadow(b, (x + a.width - 30, y + 30))
    c.save(path)
def secret(name):
    import re
    if os.environ.get(name): return os.environ[name]
    m = re.search(name + r'\s*=\s*(\S+)', open(R + '/secrets.env').read()); return m.group(1).strip('"\'') if m else None

def eleven_voice():
    """Josh's ElevenLabs voice id: cloned once from R/voice/josh_voice_sample.wav (clean teaching clips from the episodes), cached in R/elevenlabs_voice.json"""
    import urllib.request, uuid
    f = R + '/elevenlabs_voice.json'
    if os.path.exists(f): return json.load(open(f))['voice_id']
    b = '----sab' + uuid.uuid4().hex; wav = R + '/voice/josh_voice_sample.wav'
    body = (f'--{b}\r\nContent-Disposition: form-data; name="name"\r\n\r\nJosh (Super Art Bros)\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="remove_background_noise"\r\n\r\nfalse\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="josh.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode() + open(wav, 'rb').read() + f'\r\n--{b}--\r\n'.encode()
    req = urllib.request.Request('https://api.elevenlabs.io/v1/voices/add', data=body, headers={'xi-api-key': secret('ELEVENLABS_API_KEY'), 'Content-Type': 'multipart/form-data; boundary=' + b})
    vid = json.load(urllib.request.urlopen(req, timeout=180))['voice_id']; json.dump({'voice_id': vid}, open(f, 'w')); return vid

def tts(text, out, voice='ash'):
    """Voiceover. Josh's cloned voice on ElevenLabs when ELEVENLABS_API_KEY is set (SAB_TTS=openai forces the OpenAI placeholder voice)."""
    import urllib.request
    if secret('ELEVENLABS_API_KEY') and os.environ.get('SAB_TTS', 'eleven') == 'eleven':
        body = json.dumps({'text': text, 'model_id': os.environ.get('SAB_ELEVEN_MODEL', 'eleven_v4'),
                           'voice_settings': {'stability': 0.5, 'similarity_boost': 0.85}}).encode()
        req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice()}?output_format=mp3_44100_128', data=body,
                                     headers={'xi-api-key': secret('ELEVENLABS_API_KEY'), 'Content-Type': 'application/json'})
        open(out + '.raw.mp3', 'wb').write(urllib.request.urlopen(req, timeout=180).read()); src = out + '.raw.mp3'
    else:
        body = json.dumps({'model': 'gpt-4o-mini-tts', 'voice': voice, 'input': text, 'response_format': 'wav',
                           'instructions': 'Warm, upbeat dad talking to young kids on a drawing show. Curious and playful, a little amazed by the facts. Natural pace, not rushed.'}).encode()
        req = urllib.request.Request('https://api.openai.com/v1/audio/speech', data=body, headers={'Authorization': 'Bearer ' + secret('OPENAI_API_KEY'), 'Content-Type': 'application/json'})
        open(out + '.raw.wav', 'wb').write(urllib.request.urlopen(req, timeout=120).read()); src = out + '.raw.wav'
    run(['-i', src, '-af', 'silenceremove=start_periods=1:start_threshold=-45dB', '-ar', '48000', '-ac', '2', '-y', out])

def audio_norm(src_args, dur, out, music=None, fade_out=1.5):
    af = f"afade=t=out:st={max(0, dur - fade_out)}:d={fade_out},loudnorm=I=-14:TP=-2:LRA=11"
    run(src_args + ['-t', str(dur), '-af', af, '-ar', '48000', '-ac', '2', '-y', out])

if kind in ('timelapse', 'facts'):
    # Both papers sped up, cutting back and forth every SWAP seconds on the same clock (adult step, then the kid copying it).
    # Paper fills the frame on a bright sunburst; small wordmark on top; the title sits low and fades out; opens on the finished drawings + title (2 s), ends on "Draw with us today!" + both drawings.
    # facts: same, faster (SPEED), with a fun-fact voiceover (W/shorts/facts.txt -> TTS, or Josh's own recording at W/shorts/vo.wav) over a quiet music bed.
    STYLE = os.environ.get('SAB_SHORT_BG', 'blue'); MUSIC = os.environ.get('SAB_SHORT_MUSIC', SSD + '/Projects/Cartoon_Swing.m4a')
    SPEED = float(os.environ.get('SAB_SHORT_SPEED', 1.4 if kind == 'facts' else 1.0))
    SWAP, TITLE, END = float(os.environ.get('SAB_SHORT_SWAP', 3.0)) / (SPEED ** .5), 3.0, 3.5
    BOX_W, BOX_Y1 = 1060, 1700           # paper box; below ~1700 the Shorts UI covers the frame
    def source(sl, beat):
        """overhead file, paper boxes and time range of one beat in one recording"""
        Wd = os.path.join(os.path.dirname(W), sl); pr = json.load(open(Wd + '/prep.json')); cf = json.load(open(Wd + '/episode.json'))
        a0, a1 = cf['beats'][beat]; P = np.array(json.load(open(Wd + '/papers.json'))); m = (P[:, 0] >= a0) & (P[:, 0] <= a1)
        return raw(pr['top']), {'adult': np.median(P[m, 1:5], 0), 'kid': np.median(P[m, 5:9], 0)}, a0, a1
    SRC = {'draw': source(slug, 'draw'), 'color': source(CSLUG, 'montage')}
    top, boxes, c0, c1 = SRC['color']
    bg, wm_bottom = background(O + f'/bg_{STYLE}.png', STYLE); BOX_Y0 = wm_bottom + 14; BOX_H = BOX_Y1 - BOX_Y0
    title_card(O + '/title.png'); OPEN = 2.0
    art_card(bg, O + f'/open_{STYLE}.png', Image.open(O + '/title.png'))   # every Short opens on the finished artwork
    art_card(bg, O + f'/end_{STYLE}.png', Image.open(R + '/cache/lettering/short-draw-with-us-today_1.png').convert('RGBA'), end=True)
    def crop(b, aspect=BOX_W / BOX_H, pad=0.03):
        """tall crop around the paper (cover, not fit): full paper height + a little table, width from the box aspect"""
        ph = min(1.0, (b[3] - b[1]) + 2 * pad) * SH; pw = ph * aspect
        cx, cy = (b[0] + b[2]) / 2 * SW, (b[1] + b[3]) / 2 * SH
        x0 = min(max(cx - pw / 2, 0), SW - pw); y0 = min(max(cy - ph / 2, 0), SH - ph)
        return f"crop={int(pw) // 2 * 2}:{int(ph) // 2 * 2}:{int(x0)}:{int(y0)}"
    fit = f"scale={BOX_W}:{BOX_H}:force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    # keyframes are 1 s apart: decoding keyframes only gives ~1 frame per source second, i.e. a ~24x timelapse at 24 fps (SPEED drops more).
    for who in ('adult', 'kid'):
        for name, every in (('draw', 1), ('color', 3)):
            src, bx, a0, a1 = SRC[name]; p = f'{O}/{name}_{who}.mp4'
            if os.path.exists(p): continue
            run(['-skip_frame', 'nokey', '-ss', str(a0), '-t', str(a1 - a0), '-i', src, '-an', '-vf',
                 f"select='not(mod(n\\,{every}))',setpts=N/24/TB,{crop(bx[who])},{fit}",
                 '-r', '24', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-y', p + '.tmp.mp4'])
            os.rename(p + '.tmp.mp4', p)
    dur = lambda f: float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]))
    t_end = (min(dur(O + '/draw_adult.mp4'), dur(O + '/draw_kid.mp4')) + min(dur(O + '/color_adult.mp4'), dur(O + '/color_kid.mp4'))) / SPEED
    vo = None
    if kind == 'facts':
        vo = O + '/vo.wav'
        if not os.path.exists(vo): tts(open(O + '/facts.txt').read().strip(), vo)
        t_end = dur(vo) + 1.2 - OPEN  # fit the drawing to the voiceover: the ending lands right after the last line
    total = OPEN + t_end + END
    # audio: music bed (quiet under a voiceover), fade out; voiceover starts at 0.4 s, over the opener
    af = f"atrim=0:{total},afade=t=in:d=0.5,afade=t=out:st={total - 2}:d=2,loudnorm=I={-30 if vo else -19}:TP=-3"
    run(['-i', MUSIC, '-af', af, '-ar', '48000', '-ac', '2', '-y', O + '/bed.wav'])
    if vo:
        run(['-i', O + '/bed.wav', '-i', vo, '-filter_complex', '[1:a]loudnorm=I=-15:TP=-2,adelay=400|400[v];[0:a][v]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.75',
             '-ar', '48000', '-y', O + '/tl_audio.wav'])
    else: os.replace(O + '/bed.wav', O + '/tl_audio.wav')
    kid_on = f"lt(t,{t_end})*eq(mod(floor(t/{SWAP:.3f}),2),1)"
    cy = f"{BOX_Y0}+({BOX_H}-h)/2"; sp = f"setpts=PTS/{SPEED}," if SPEED != 1 else ''
    # stretch to t_end if the voiceover is longer than the sped-up drawing
    nat = (min(dur(O + '/draw_adult.mp4'), dur(O + '/draw_kid.mp4')) + min(dur(O + '/color_adult.mp4'), dur(O + '/color_kid.mp4')))
    sp = f"setpts=PTS*{t_end / nat:.4f},fps=24,"
    def wh(n):  # split episodes: the coloring recording's crop can differ slightly in size, so match it to the drawing clip
        return subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height', '-of', 'csv=p=0:s=x', f'{O}/{n}.mp4']).decode().strip().replace('x', ':')
    out = f'{O}/{slug}-{kind}-{STYLE}.mp4'; enc = ['-r', '24', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p']
    run(['-loop', '1', '-t', str(OPEN), '-i', O + f'/open_{STYLE}.png', '-vf', f'fade=t=out:st={OPEN - 0.2}:d=0.2:color=white'] + enc + ['-y', O + '/v_open.mp4'])
    run(['-loop', '1', '-i', O + f'/bg_{STYLE}.png', '-i', O + '/draw_adult.mp4', '-i', O + '/color_adult.mp4', '-i', O + '/draw_kid.mp4', '-i', O + '/color_kid.mp4',
         '-loop', '1', '-i', O + f'/end_{STYLE}.png', '-filter_complex',
         f"[2:v]scale={wh('draw_adult')},setsar=1[ca];[4:v]scale={wh('draw_kid')},setsar=1[ck];[1:v]setsar=1[da];[3:v]setsar=1[dk];"
         f"[da][ca]concat=n=2:v=1,{sp}null[pa];[dk][ck]concat=n=2:v=1,{sp}null[pk];"
         f"[0:v][pa]overlay=(W-w)/2:{cy}:eof_action=pass[a];[a][pk]overlay=(W-w)/2:{cy}:eof_action=pass:enable='{kid_on}'[b];"
         f"[5:v]format=rgba,fade=t=in:st={t_end}:d=0.35:alpha=1[e];[b][e]overlay=0:0:enable='gte(t,{t_end})',format=yuv420p[v]",
         '-map', '[v]', '-t', str(t_end + END)] + enc + ['-y', O + '/v_main.mp4'])
    open(O + '/v_list.txt', 'w').write(f"file '{O}/v_open.mp4'\nfile '{O}/v_main.mp4'\n")
    run(['-f', 'concat', '-safe', '0', '-i', O + '/v_list.txt', '-i', O + '/tl_audio.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
         '-c:a', 'aac', '-b:a', '160k', '-t', str(total), '-movflags', '+faststart', '-y', out])
    print(kind, round(total, 2), 's ->', out)

elif kind == 'moment':
    # The kid's funny moment: opens on the finished drawings + title (2 s), then the front camera tight on the kid with big captions
    # (dialogue at full level, quiet music bed), ends on the locked end card (big wordmark, both drawings, "Draw with us today!").
    # raw_a/raw_b and caption times are dialogue seconds (W/dlg48.wav; the front video is at +prep offset).
    a, b = float(sys.argv[3]), float(sys.argv[4]); caps = json.load(open(sys.argv[5])); name = sys.argv[6] if len(sys.argv) > 6 else 'moment'
    STYLE = os.environ.get('SAB_SHORT_BG', 'yellow'); MUSIC = os.environ.get('SAB_SHORT_MUSIC', SSD + '/Projects/Cartoon_Swing.m4a')
    OPEN, END = 2.0, 3.0; dur_m = b - a; total = OPEN + dur_m + END
    bg, _ = background(O + f'/bg_{STYLE}.png', STYLE); title_card(O + '/title.png')
    art_card(bg, O + f'/open_{STYLE}.png', Image.open(O + '/title.png'))
    art_card(bg, O + f'/end_{STYLE}.png', Image.open(R + '/cache/lettering/short-draw-with-us-today_1.png').convert('RGBA'), end=True)
    front = raw(prep['front']); off = prep['offset']; hb = cfg['head_boxes']['kid']
    Z = float(os.environ.get('SAB_MOMENT_ZOOM', 1.35))                     # 9:16 crop, Z times tighter than full height, centred on the kid's head box
    ch = int(SH / Z) // 2 * 2; cw = int(ch * VW / VH) // 2 * 2
    cx = (hb[0] + hb[2]) / 2 * SW; x0 = int(min(max(cx - cw / 2, 0), SW - cw)) // 2 * 2
    cy = (hb[1] + hb[3]) / 2 * SH; y0 = int(min(max(cy - ch / 2, 0), SH - ch)) // 2 * 2
    def t(s):  # ASS time
        s = max(0, s); return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
    ass = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {VW}", f"PlayResY: {VH}", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           "Style: Cap,Permanent Marker,100,&H00F0E2C8,&H000000FF,&H00301A0D,&H64000000,0,0,0,0,100,100,1,0,1,10,5,2,40,40,300,1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for s0, s1, txt in caps: ass.append(f"Dialogue: 0,{t(s0 - a)},{t(min(s1, b) - a)},Cap,,0,0,0,,{txt}")
    open(O + f'/{name}.ass', 'w').write('\n'.join(ass))
    # audio: dialogue at -16 LUFS over a quiet bed (louder under the cards)
    run(['-ss', str(a), '-t', str(dur_m), '-i', W + '/dlg48.wav', '-af', 'afade=t=in:d=0.08,afade=t=out:st=%.2f:d=0.25,loudnorm=I=-16:TP=-2,adelay=%d|%d' % (dur_m - 0.25, OPEN * 1000, OPEN * 1000),
         '-ar', '48000', '-ac', '2', '-y', O + f'/{name}_dlg.wav'])
    vol = f"volume='if(between(t,{OPEN - 0.3},{OPEN + dur_m}),0.25,1)':eval=frame"
    run(['-i', MUSIC, '-af', f"atrim=0:{total},loudnorm=I=-21:TP=-3,{vol},afade=t=in:d=0.3,afade=t=out:st={total - 1.5}:d=1.5", '-ar', '48000', '-ac', '2', '-y', O + f'/{name}_bed.wav'])
    run(['-i', O + f'/{name}_bed.wav', '-i', O + f'/{name}_dlg.wav', '-filter_complex', '[0:a][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.8', '-ar', '48000', '-y', O + f'/{name}_audio.wav'])
    enc = ['-r', '24', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p']
    run(['-loop', '1', '-t', str(OPEN), '-i', O + f'/open_{STYLE}.png', '-vf', f'fade=t=out:st={OPEN - 0.2}:d=0.2:color=white'] + enc + ['-y', O + f'/{name}_v_open.mp4'])
    vf = (('hflip,vflip,' if prep['flip_front'] else '') + f"fps=24,crop={cw}:{ch}:{x0}:{y0},scale={VW}:{VH}:flags=lanczos,fade=t=in:d=0.2:color=white,subtitles={O}/{name}.ass:fontsdir={FONTS}")
    run(['-ss', str(a + off), '-t', str(dur_m), '-i', front, '-an', '-vf', vf] + enc + ['-y', O + f'/{name}_v_mid.mp4'])
    run(['-loop', '1', '-t', str(END), '-i', O + f'/end_{STYLE}.png', '-vf', 'fade=t=in:d=0.3'] + enc + ['-y', O + f'/{name}_v_end.mp4'])
    open(O + f'/{name}_list.txt', 'w').write(''.join(f"file '{O}/{name}_v_{k}.mp4'\n" for k in ('open', 'mid', 'end')))
    out = f'{O}/{slug}-{name}-{STYLE}.mp4'
    run(['-f', 'concat', '-safe', '0', '-i', O + f'/{name}_list.txt', '-i', O + f'/{name}_audio.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
         '-c:a', 'aac', '-b:a', '160k', '-t', str(total), '-movflags', '+faststart', '-y', out])
    print('moment', round(total, 2), 's ->', out)
