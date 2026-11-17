"""QA, part 2 (container): automated checks on a packed episode (see sab_qa.py), independent of the edit plan.
usage: sab_qa_check.py <pack_dir> [haar_dir]
writes <pack_dir>/words.json (word-level transcript) and <pack_dir>/check_report.json + check_report.md"""
import json, os, re, sys, glob, wave
import numpy as np, cv2

P = sys.argv[1]
HAAR = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('SAB_HAAR', '.')   # folder holding haar_frontalface_default.xml + haar_profileface.xml
M = json.load(open(P + '/measure.json'))
meta, audio, cuts = M['meta'], M['audio'], M['cuts']
D = meta['video_s']
F = []  # findings: dict(sev, check, t, msg)
def add(sev, check, t, msg): F.append(dict(sev=sev, check=check, t=None if t is None else round(t, 2), msg=msg))
def ts(t): return '%d:%05.2f' % (t // 60, t % 60)

# 1. picture/sound length
d = meta['audio_s'] - meta['video_s']
if abs(d) > 0.05: add('high', 'av_length', None, f'audio and video lengths differ by {d:+.3f} s')

# 2. loudness (target -14 LUFS integrated, peaks at or below -1 dBTP)
I, TP = audio.get('integrated_lufs'), audio.get('true_peak_dbtp')
if I is not None and abs(I + 14) > 1.0: add('medium', 'loudness', None, f'integrated loudness {I} LUFS (target -14 ±1)')
if TP is not None and TP > -1.0: add('medium', 'true_peak', None, f'true peak {TP} dBTP (limit -1.0)')

# 3. black and frozen picture (the iris has a deliberate ~0.1 s black beat; the outro is a looped clip)
for a, b in M['black']:
    if b - a > 0.3: add('high', 'black', a, f'{b - a:.2f} s of black frames at {ts(a)}')
for t in M['frozen']:
    if t < D - 14: add('medium', 'frozen', t, f'picture frozen for 2.5 s+ starting {ts(t)}')

# 4. word-level transcript
wp = P + '/words.json'
if not os.path.exists(wp):
    from faster_whisper import WhisperModel
    w = wave.open(P + '/speech16k.wav'); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    m = WhisperModel('small.en', device='cpu', compute_type='int8')
    segs, _ = m.transcribe(x, word_timestamps=True, vad_filter=True)
    words = [dict(w=ww.word.strip(), s=round(ww.start, 2), e=round(ww.end, 2)) for s in segs for ww in s.words]
    json.dump(words, open(wp, 'w'))
words = json.load(open(wp))
norm = lambda s: re.sub(r'[^a-z0-9\']', '', s.lower())

# 5. speech around every cut: repeated phrases, chopped words, dead air
SPEED = []  # montage cuts (no speech expected) are skipped by the silence rule when the music is playing
for c in cuts:
    near = [w for w in words if c - 4 <= w['s'] <= c + 4]
    before = [norm(w['w']) for w in near if w['e'] <= c + 0.05]
    after = [norm(w['w']) for w in near if w['s'] >= c - 0.05]
    for n in (4, 3, 2):
        tail = before[-n:]
        if len(tail) == n and all(tail) and after[:n] == tail:
            add('high', 'repeat_at_cut', c, f'"{" ".join(tail)}" is said right before and right after the cut at {ts(c)}'); break
        found = False
        for k in range(1, len(after) - n + 1):
            if k <= 4 and after[k:k + n] == tail and all(tail):
                add('high', 'repeat_at_cut', c, f'"{" ".join(tail)}" repeats within a few words after the cut at {ts(c)}'); found = True; break
        if found: break
    for w in near:
        if w['s'] < c - 0.12 and w['e'] > c + 0.12 and len(norm(w['w'])) > 2:
            add('medium', 'chopped_word', c, f'the word "{w["w"]}" spans the cut at {ts(c)} and may be chopped')
for a, b in audio['silences']:
    for c in cuts:
        if a - 0.4 <= c <= b + 0.4 and b - a >= 0.6:
            add('medium', 'dead_air_at_cut', c, f'{b - a:.2f} s of near-silence at the cut at {ts(c)}'); break

# 6. on-screen title vs faces (the title is found by its colours: cream fill next to a plum outline)
fd = cv2.CascadeClassifier(HAAR + '/haar_frontalface_default.xml'); pd = cv2.CascadeClassifier(HAAR + '/haar_profileface.xml')
worst = 0
for f in sorted(glob.glob(P + '/t000*.jpg')):
    t = int(os.path.basename(f)[1:6]); im = cv2.imread(f); hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    cream = (hsv[..., 0] >= 10) & (hsv[..., 0] <= 30) & (hsv[..., 1] > 25) & (hsv[..., 1] < 110) & (hsv[..., 2] > 200)
    plum = ((hsv[..., 0] >= 150) | (hsv[..., 0] <= 8)) & (hsv[..., 1] > 60) & (hsv[..., 2] < 110)
    title = cream & (cv2.dilate(plum.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0)
    if title.sum() < 600: continue                                                # no title on screen
    title = cv2.morphologyEx(title.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(title)                      # keep lettering-sized regions only (drops specks on hands, markers)
    if n < 2: continue
    big = 1 + int(np.argmax(st[1:, 4])); bx, by, bw, bh = st[big, :4]
    keep = [i for i in range(1, n) if i == big or (st[i, 4] >= 60 and bx - 60 <= st[i, 0] <= bx + bw + 60 and by - 140 <= st[i, 1] <= by + bh + 60)]
    title = np.isin(lab, keep).astype(np.uint8)                                   # the title block = the biggest lettering run + its neighbours
    if title.sum() < 600: continue
    g = cv2.cvtColor(cv2.resize(im, None, fx=2, fy=2), cv2.COLOR_BGR2GRAY)
    faces = [tuple(int(v / 2) for v in r) for r in list(fd.detectMultiScale(g, 1.08, 4, minSize=(36, 36))) + list(pd.detectMultiScale(g, 1.08, 4, minSize=(36, 36)))]
    for x, y, w, h in faces:
        if y + h / 2 > 0.62 * im.shape[0]: continue                                # low in frame: shirt prints, not heads
        # head = face box grown upward for hair
        x0, y0, x1, y1 = max(0, x - w // 6), max(0, y - h // 3), min(im.shape[1], x + w + w // 6), min(im.shape[0], y + int(h * 0.9))
        ov = title[y0:y1, x0:x1].mean()
        worst = max(worst, ov)
        if ov > 0.03: add('high', 'title_over_face', t, f'title lettering covers {ov:.0%} of a face at {ts(t)}')
dedup = {}
for f in F: dedup.setdefault((f['check'], f['t'], f['msg']), f)
F = sorted(dedup.values(), key=lambda f: ({'high': 0, 'medium': 1, 'low': 2}[f['sev']], f['t'] or 0))
rep = dict(file=meta['file'], duration=D, cuts=len(cuts), words=len(words), findings=F,
           summary=dict(high=sum(f['sev'] == 'high' for f in F), medium=sum(f['sev'] == 'medium' for f in F)))
json.dump(rep, open(P + '/check_report.json', 'w'), indent=1)
md = [f"# Automated checks: {meta['file']}", f"{D / 60:.1f} min, {len(cuts)} cuts, loudness {I} LUFS, peak {TP} dBTP", '']
md += [f"- **{f['sev']}** · {f['check']} · {ts(f['t']) if f['t'] is not None else '—'} · {f['msg']}" for f in F] or ['- no issues found']
open(P + '/check_report.md', 'w').write('\n'.join(md) + '\n')
print('\n'.join(md))
