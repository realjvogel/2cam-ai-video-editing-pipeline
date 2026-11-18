"""YouTube Shorts (1080x1920, made for kids) from an episode's raw footage.
usage:
  sab_shorts.py <slug> timelapse                       both papers stacked, drawing -> coloring -> hold, title + rag
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

def background(path, title=True):
    """wood plate filling 9:16 + wordmark + 'How to draw a' + subject at the top"""
    pl = Image.open(R + '/cache/plates/wood-clean_0.png').convert('RGB'); s = VH / pl.height
    pl = pl.resize((int(pl.width * s), VH), Image.LANCZOS); x = (pl.width - VW) // 2
    bg = ImageEnhance.Brightness(pl.crop((x, 0, x + VW, VH)).filter(ImageFilter.GaussianBlur(28))).enhance(0.55).convert('RGBA')   # soft, dark wood so the title and paper pop
    if title:
        wm = Image.open(A + '/super-art-bros-wordmark-light.png').convert('RGBA'); wm = wm.resize((300, int(wm.height * 300 / wm.width)), Image.LANCZOS)
        bg.alpha_composite(wm, (VW // 2 - 150, 24))
        hd = Image.open(A + '/' + edl.get('header', 'video-how-to-draw-a.png')).convert('RGBA'); hd = hd.resize((760, int(hd.height * 760 / hd.width)), Image.LANCZOS)
        bg.alpha_composite(hd, (VW // 2 - 380, 24 + wm.height + 6))
        sb = Image.open(E + '/subject-aligned.png').convert('RGBA'); sb = sb.resize((820, int(sb.height * 820 / sb.width)), Image.LANCZOS)
        bg.alpha_composite(sb, (VW // 2 - 410, 24 + wm.height + 6 + hd.height - 30))
        bg._title_bottom = 24 + wm.height + 6 + hd.height - 30 + sb.height
    bg.save(path); return getattr(bg, '_title_bottom', 0)

def audio_norm(src_args, dur, out, music=None, fade_out=1.5):
    af = f"afade=t=out:st={max(0, dur - fade_out)}:d={fade_out},loudnorm=I=-14:TP=-2:LRA=11"
    run(src_args + ['-t', str(dur), '-af', af, '-ar', '48000', '-ac', '2', '-y', out])

if kind == 'timelapse':
    top = raw(prep['top']); d0, d1 = cfg['beats']['draw']; c0, c1 = cfg['beats']['montage']
    P = np.array(json.load(open(W + '/papers.json'))); m = (P[:, 0] >= d0) & (P[:, 0] <= c1)
    L = np.median(P[m, 1:5], 0); Rb = np.median(P[m, 5:9], 0)
    def crop(b, pad=0.015):
        x0, y0, x1, y1 = max(0, b[0] - pad), max(0, b[1] - pad), min(1, b[2] + pad), min(1, b[3] + pad)
        return f"crop={int((x1 - x0) * 3840) // 2 * 2}:{int((y1 - y0) * 2160) // 2 * 2}:{int(x0 * 3840)}:{int(y0 * 2160)},scale=1000:-2"
    tb = background(O + '/bg.png')
    # keyframes are 1 s apart: decoding keyframes only gives ~1 frame per source second, i.e. a ~24x timelapse at 24 fps.
    # The adult's paper fills the frame (that's the step-by-step); both finished drawings side by side at the end.
    for name, a, b, every in (('draw', d0, d1, 1), ('color', c0, c1, 3)):
        p = f'{O}/{name}.mp4'
        if os.path.exists(p): continue
        run(['-skip_frame', 'nokey', '-ss', str(a), '-t', str(b - a), '-i', top, '-an', '-vf',
             f"select='not(mod(n\\,{every}))',setpts=N/24/TB,{crop(L)}",
             '-r', '24', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-y', p + '.tmp.mp4'])
        os.rename(p + '.tmp.mp4', p)
    END = 3.0; pe = f'{O}/end.mp4'
    if not os.path.exists(pe):
        run(['-ss', str(c1 - 1.5), '-i', top, '-frames:v', '1', '-an', '-vf',
             f"split[a][b];[a]{crop(L).replace('scale=1000:-2', 'scale=-2:560')}[l];[b]{crop(Rb).replace('scale=1000:-2', 'scale=-2:560')}[r];"
             f"[l]pad=iw+16:ih:0:0:color=0x3a2a1c[l2];[l2][r]hstack=inputs=2:shortest=1", '-y', O + '/end.png'])
        run(['-loop', '1', '-i', O + '/end.png', '-t', str(END), '-r', '24', '-vf', 'pad=1000:ih:(ow-iw)/2:0,format=yuv420p',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-y', pe])
    dur = lambda f: float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]))
    t_end = dur(O + '/draw.mp4') + dur(O + '/color.mp4'); total = t_end + END
    audio_norm(['-i', W + '/music48.wav'], total, O + '/tl_audio.wav')
    def hgt(f): return int(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=height', '-of', 'csv=p=0', f]).decode().strip())
    y = tb + max(10, (VH - tb - hgt(O + '/draw.mp4')) // 2); ye = tb + 40
    ass = O + '/tl.ass'
    open(ass, 'w').write("\n".join(["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {VW}", f"PlayResY: {VH}", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: End,Permanent Marker,112,&H00F0E2C8,&H000000FF,&H00301A0D,&H64000000,0,0,0,0,100,100,1,0,1,9,4,2,60,60,170,1", "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        f"Dialogue: 0,0:00:{t_end:05.2f},0:00:{total:05.2f},End,,0,0,0,,DRAW YOURS!\\NFULL LESSON ON\\NOUR CHANNEL"]))
    run(['-loop', '1', '-i', O + '/bg.png', '-i', O + '/draw.mp4', '-i', O + '/color.mp4', '-i', pe, '-i', O + '/tl_audio.wav', '-filter_complex',
         f"[1:v][2:v]concat=n=2:v=1[p];[0:v][p]overlay=40:{y}:eof_action=pass[a];[a][3:v]overlay=40:{ye}:enable='gte(t,{t_end})',"
         f"subtitles={ass}:fontsdir={FONTS},format=yuv420p[v]", '-map', '[v]', '-map', '4:a',
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
