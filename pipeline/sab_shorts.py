"""YouTube Shorts (1080x1920, made for kids) from an episode's raw footage.
usage:
  sab_shorts.py <slug> timelapse                       both papers sped up, cutting adult <-> kid every 3 s (SAB_SHORT_SWAP), small wordmark, title fades, both drawings at the end
  sab_shorts.py <slug> moment <raw_a> <raw_b> <captions.json> [name]
        front camera cropped tight on the kid, big captions, end card. captions.json: [[raw_t0, raw_t1, "TEXT"], ...]
Output: W/shorts/<slug>-<kind>.mp4 (and copied to SAB - auto edits/Shorts/ by the caller)."""
import os, sys, json, subprocess, numpy as np
from PIL import Image, ImageFilter, ImageEnhance
slug, kind = sys.argv[1], sys.argv[2]
SSD = os.path.expanduser(os.environ.get('SAB_SSD', '~/sab-data')); R = SSD + '/SAB-production'; E = f'{R}/episodes/{slug}'
W = os.path.join(os.path.expanduser(os.environ.get('SAB_WORK', '~/sab/eps')), slug); O = W + '/shorts'; os.makedirs(O, exist_ok=True)
prep = json.load(open(W + '/prep.json')); edl = json.load(open(W + '/edl.json')); cfg = json.load(open(W + '/episode.json'))
FONTS = R + '/promo/fonts'; A = R + '/assets/look-c'
def run(a): subprocess.run(['ffmpeg', '-nostdin', '-v', 'error'] + a, check=True)
def raw(p):
    if os.path.exists(p): return p
    return SSD + p.split('data drive', 1)[1]
VW, VH = 1080, 1920

def background(path):
    """soft dark wood filling 9:16 with a small wordmark at the top"""
    pl = Image.open(R + '/cache/plates/wood-clean_0.png').convert('RGB'); s = VH / pl.height
    pl = pl.resize((int(pl.width * s), VH), Image.LANCZOS); x = (pl.width - VW) // 2
    bg = ImageEnhance.Brightness(pl.crop((x, 0, x + VW, VH)).filter(ImageFilter.GaussianBlur(28))).enhance(0.55).convert('RGBA')
    wm = Image.open(A + '/super-art-bros-wordmark-light.png').convert('RGBA'); wm = wm.resize((230, int(wm.height * 230 / wm.width)), Image.LANCZOS)
    bg.alpha_composite(wm, (VW // 2 - 115, 26)); bg.save(path); return 26 + wm.height

def title_card(path, width=900):
    """'How to draw a' + subject, transparent, shown over the bottom of the paper for the first seconds"""
    hd = Image.open(A + '/' + edl.get('header', 'video-how-to-draw-a.png')).convert('RGBA'); hd = hd.resize((int(width * .85), int(hd.height * width * .85 / hd.width)), Image.LANCZOS)
    sb = Image.open(E + '/subject-aligned.png').convert('RGBA'); sb = sb.resize((width, int(sb.height * width / sb.width)), Image.LANCZOS)
    im = Image.new('RGBA', (width, hd.height + sb.height - 30)); im.alpha_composite(hd, ((width - hd.width) // 2, 0)); im.alpha_composite(sb, (0, hd.height - 30))
    im.save(path); return im.height

def audio_norm(src_args, dur, out, music=None, fade_out=1.5):
    af = f"afade=t=out:st={max(0, dur - fade_out)}:d={fade_out},loudnorm=I=-14:TP=-2:LRA=11"
    run(src_args + ['-t', str(dur), '-af', af, '-ar', '48000', '-ac', '2', '-y', out])

if kind == 'timelapse':
    # Both papers sped up, cutting back and forth every SWAP seconds on the same clock (adult step, then the kid copying it).
    # Paper fills the frame; small wordmark on top; the title sits low and fades out after TITLE seconds; both drawings side by side at the end.
    SWAP, TITLE, END = float(os.environ.get('SAB_SHORT_SWAP', 3.0)), 3.5, 3.0
    BOX_W, BOX_Y0, BOX_Y1 = 1060, 0, 1700           # paper box; below ~1700 the Shorts UI covers the frame
    top = raw(prep['top']); d0, d1 = cfg['beats']['draw']; c0, c1 = cfg['beats']['montage']
    P = np.array(json.load(open(W + '/papers.json'))); m = (P[:, 0] >= d0) & (P[:, 0] <= c1)
    boxes = {'adult': np.median(P[m, 1:5], 0), 'kid': np.median(P[m, 5:9], 0)}
    wm_bottom = background(O + '/bg.png'); BOX_Y0 = wm_bottom + 14; BOX_H = BOX_Y1 - BOX_Y0
    th = title_card(O + '/title.png')
    def crop(b, aspect=BOX_W / BOX_H, pad=0.03):
        """tall crop around the paper (cover, not fit): full paper height + a little table, width from the box aspect"""
        ph = min(1.0, (b[3] - b[1]) + 2 * pad) * 2160; pw = ph * aspect
        cx, cy = (b[0] + b[2]) / 2 * 3840, (b[1] + b[3]) / 2 * 2160
        x0 = min(max(cx - pw / 2, 0), 3840 - pw); y0 = min(max(cy - ph / 2, 0), 2160 - ph)
        return f"crop={int(pw) // 2 * 2}:{int(ph) // 2 * 2}:{int(x0)}:{int(y0)}"
    fit = f"scale={BOX_W}:{BOX_H}:force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2"
    # keyframes are 1 s apart: decoding keyframes only gives ~1 frame per source second, i.e. a ~24x timelapse at 24 fps.
    for who, b in boxes.items():
        for name, a0, a1, every in (('draw', d0, d1, 1), ('color', c0, c1, 3)):
            p = f'{O}/{name}_{who}.mp4'
            if os.path.exists(p): continue
            run(['-skip_frame', 'nokey', '-ss', str(a0), '-t', str(a1 - a0), '-i', top, '-an', '-vf',
                 f"select='not(mod(n\\,{every}))',setpts=N/24/TB,{crop(b)},{fit}",
                 '-r', '24', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-y', p + '.tmp.mp4'])
            os.rename(p + '.tmp.mp4', p)
    pe = f'{O}/end2.mp4'
    if not os.path.exists(pe):
        run(['-ss', str(c1 - 1.5), '-i', top, '-frames:v', '1', '-an', '-vf',
             f"split[a][b];[a]{crop(boxes['adult'], 0.72, 0.012)},scale=-2:900[l];[b]{crop(boxes['kid'], 0.72, 0.012)},scale=-2:900[r];"
             f"[l]pad=iw+20:ih:0:0:color=0x3a2a1c[l2];[l2][r]hstack=inputs=2:shortest=1,scale='min(iw,{BOX_W})':-2", '-y', O + '/end2.png'])
        run(['-loop', '1', '-i', O + '/end2.png', '-t', str(END), '-r', '24', '-vf', 'format=yuv420p',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-y', pe])
    dur = lambda f: float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]))
    t_end = min(dur(O + '/draw_adult.mp4'), dur(O + '/draw_kid.mp4')) + min(dur(O + '/color_adult.mp4'), dur(O + '/color_kid.mp4')); total = t_end + END
    audio_norm(['-i', W + '/music48.wav'], total, O + '/tl_audio.wav')
    end_top = BOX_Y0 + 60; end_y = end_top + int(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=height', '-of', 'csv=p=0', pe]).decode().strip())
    ass = O + '/tl.ass'
    open(ass, 'w').write("\n".join(["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {VW}", f"PlayResY: {VH}", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: End,Permanent Marker,96,&H00F0E2C8,&H000000FF,&H00301A0D,&H64000000,0,0,0,0,100,100,1,0,1,9,4,8,60,60,{end_y + 40},1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,0:00:{t_end:05.2f},0:00:{total:05.2f},End,,0,0,0,,DRAW YOURS!\\NFULL LESSON ON OUR CHANNEL"]))
    kid_on = f"lt(t,{t_end})*eq(mod(floor(t/{SWAP}),2),1)"
    cy = f"{BOX_Y0}+({BOX_H}-h)/2"
    run(['-loop', '1', '-i', O + '/bg.png', '-i', O + '/draw_adult.mp4', '-i', O + '/color_adult.mp4', '-i', O + '/draw_kid.mp4', '-i', O + '/color_kid.mp4',
         '-i', pe, '-loop', '1', '-i', O + '/title.png', '-i', O + '/tl_audio.wav', '-filter_complex',
         f"[1:v][2:v]concat=n=2:v=1[pa];[3:v][4:v]concat=n=2:v=1[pk];"
         f"[0:v][pa]overlay=(W-w)/2:{cy}:eof_action=pass[a];[a][pk]overlay=(W-w)/2:{cy}:eof_action=pass:enable='{kid_on}'[b];"
         f"[b][5:v]overlay=(W-w)/2:{end_top}:enable='gte(t,{t_end})'[c];"
         f"[6:v]format=rgba,fade=t=out:st={TITLE}:d=0.6:alpha=1[ti];[c][ti]overlay=(W-w)/2:{BOX_Y1}-{th}+40:shortest=0:enable='lt(t,{TITLE + 0.7})',"
         f"subtitles={ass}:fontsdir={FONTS},format=yuv420p[v]", '-map', '[v]', '-map', '7:a',
         '-t', str(total), '-r', '24', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-y', f'{O}/{slug}-timelapse.mp4'])
    print('timelapse', round(total, 2), 's ->', f'{O}/{slug}-timelapse.mp4')

elif kind == 'moment':
    a, b = float(sys.argv[3]), float(sys.argv[4]); caps = json.load(open(sys.argv[5])); name = sys.argv[6] if len(sys.argv) > 6 else 'moment'
    front = raw(prep['front']); off = prep['offset']; hb = cfg['head_boxes']['kid']
    cx = (hb[0] + hb[2]) / 2 * 3840; cy = ((hb[1] + hb[3]) / 2 + 0.02) * 2160; ch = 1778; cw = 1000
    x0 = int(min(max(cx - cw / 2, 0), 3840 - cw)) // 2 * 2; y0 = int(min(max(cy - ch / 2, 0), 2160 - ch)) // 2 * 2
    end = 2.6; dur = b - a
    def t(s):  # ASS time
        s = max(0, s); return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"
    ass = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {VW}", f"PlayResY: {VH}", "", "[V4+ Styles]",
           "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
           "Style: Cap,Permanent Marker,92,&H00F0E2C8,&H000000FF,&H00301A0D,&H64000000,0,0,0,0,100,100,1,0,1,9,4,2,60,60,330,1",
           "Style: End,Permanent Marker,84,&H00F0E2C8,&H000000FF,&H00301A0D,&H64000000,0,0,0,0,100,100,1,0,1,9,4,5,60,60,0,1",
           "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for s0, s1, txt in caps: ass.append(f"Dialogue: 0,{t(s0 - a)},{t(min(s1, b) - a)},Cap,,0,0,0,,{txt}")
    ass.append(f"Dialogue: 0,{t(dur)},{t(dur + end)},End,,0,0,0,,FULL LESSON\\NON OUR CHANNEL!\\N✏️ SUPER ART BROS")
    open(O + f'/{name}.ass', 'w').write('\n'.join(ass))
    # audio: dialogue (with the episode's duck ranges), then silence under the end card
    import wave
    w = wave.open(W + '/dlg48.wav'); SR = w.getframerate(); ch_n = w.getnchannels()
    w.setpos(int(a * SR)); x = np.frombuffer(w.readframes(int(dur * SR)), np.int16).astype(np.float32).reshape(-1, ch_n)
    for d_a, d_b, db in cfg.get('duck', []):
        i0, i1 = int((d_a - a) * SR), int((d_b - a) * SR)
        if i1 > 0 and i0 < len(x): x[max(0, i0):max(0, i1)] *= 10 ** (db / 20)
    x = np.concatenate([x, np.zeros((int(end * SR), ch_n), np.float32)])
    o = wave.open(O + f'/{name}_raw.wav', 'wb'); o.setnchannels(ch_n); o.setsampwidth(2); o.setframerate(SR); o.writeframes(np.clip(x, -32768, 32767).astype(np.int16).tobytes()); o.close()
    audio_norm(['-i', O + f'/{name}_raw.wav'], dur + end, O + f'/{name}_audio.wav', fade_out=0.6)
    vf = (('hflip,vflip,' if prep['flip_front'] else '') + f"fps=24,crop={cw}:{ch}:{x0}:{y0},scale={VW}:{VH},"
          f"tpad=stop_mode=clone:stop_duration={end},eq=brightness=0:enable='gte(t,{dur})',"
          f"boxblur=20:enable='gte(t,{dur})',subtitles={O}/{name}.ass:fontsdir={FONTS}")
    run(['-ss', str(a + off), '-t', str(dur), '-i', front, '-i', O + f'/{name}_audio.wav', '-map', '0:v', '-map', '1:a', '-vf', vf,
         '-t', str(dur + end), '-r', '24', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-y', f'{O}/{slug}-{name}.mp4'])
    print('moment', round(dur + end, 2), 's ->', f'{O}/{slug}-{name}.mp4')
