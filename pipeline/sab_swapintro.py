"""Swap a new intro into a delivered final (e.g. a cut restored or removed inside the intro), keeping everything
after it as delivered.
usage: SAB_OLD_FIRST=<seconds of the old intro's first uncut piece> sab_swapintro.py <slug> <old_final.mp4> <new_final.mp4> <old_intro_seconds> <old_title_out_local>
Needs W/vo/intro.mp4 (new) and W/vo/wipe.mp4, W/mix.wav (the episode's pre-loudness mix, which starts with the
same stinger + welcome), W/dlg48.wav, W/edl.json (new intro keep ranges), W/finalize.json (bug timing).
Video: new intro (+ wordmark bug from the new title end) + old final from the old intro's end; only the stretch up
to the next keyframe is re-encoded. Audio: the new intro's dialogue from dlg48 for every kept piece, plus the music sting taken from the old mix
(mix - dialogue over the old intro's first uncut piece), level-matched to the delivered mix, then the
delivered audio from the old intro's end."""
import json, os, sys, subprocess, wave, tempfile, numpy as np
slug, old, new, old_intro, old_tout = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
W = os.path.join(os.path.expanduser(os.environ.get('SAB_WORK', '~/sab/eps')), slug)
A = os.path.join(os.path.expanduser(os.environ.get('SAB_SSD', '~/sab-data')), 'SAB-production', 'assets', 'look-c')
edl = json.load(open(W + '/edl.json')); K = edl.get('out_k', 1); F = json.load(open(W + '/finalize.json'))
seg = [s for s in edl['segments'] if s['role'] == 'intro'][0]; keep = seg.get('keep') or [[seg['a'], seg['b']]]
T = tempfile.mkdtemp(dir=W); SR = 48000
def duck(x, edl, SR=48000):
    """Lower the dialogue in edl['duck'] ranges ([raw_a, raw_b, dB], e.g. the adult's short reply) instead of cutting it,
    so the picture stays continuous. 60 ms ramps."""
    x = x.copy(); r = int(0.06 * SR)
    for a, b, db in edl.get('duck', []):
        i0, i1 = int(a * SR), int(b * SR); g = 10 ** (db / 20); env = np.ones(i1 - i0 + 2 * r, np.float32) * g
        env[:r] = np.linspace(1, g, r); env[-r:] = np.linspace(g, 1, r); j0 = max(0, i0 - r); env = env[j0 - (i0 - r):]
        x[j0:j0 + len(env)] *= env[:len(x) - j0, None]
    return x
def run(a): subprocess.run(['ffmpeg', '-nostdin', '-v', 'error'] + a, check=True)
def vdur(f): return float(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=duration', '-of', 'csv=p=0', f]))
def rd(p): w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32).reshape(-1, w.getnchannels())
new_intro = vdur(W + '/vo/intro.mp4'); bug_on = F['bug_on'] + (edl['title']['t_out_local'] - old_tout)
enc = ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '24']
# 1) new intro with the bug from the new title end
run(['-i', W + '/vo/intro.mp4', '-i', A + '/wordmark_bug_corner.png', '-filter_complex',
     f"[1:v]scale=iw*{K}:ih*{K}[bug];[0:v][bug]overlay=0:0:enable='gte(t,{bug_on})',format=yuv420p[v]", '-map', '[v]'] + enc + ['-y', T + '/a.mp4'])
# 2) old final from the old intro end to the next keyframe (re-encoded), then copied
kf = [float(l.split(',')[0]) for l in subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'packet=pts_time,flags', '-of', 'csv=p=0', old]).decode().split() if ',K' in l and l.split(',')[0] not in ('', 'N/A')]
kb = min(k for k in kf if k > old_intro + 0.5)
run(['-ss', str(old_intro), '-i', old, '-map', '0:v', '-frames:v', str(int(round((kb - old_intro) * 24)))] + enc + ['-y', T + '/b.mp4'])
run(['-ss', str(kb + 0.01), '-i', old, '-map', '0:v', '-c', 'copy', '-y', T + '/c.mp4'])
ts = []
for p in ('a', 'b', 'c'):
    run(['-i', f'{T}/{p}.mp4', '-c', 'copy', '-bsf:v', 'h264_mp4toannexb', '-f', 'mpegts', '-y', f'{T}/{p}.ts']); ts.append(f'{T}/{p}.ts')
run(['-i', 'concat:' + '|'.join(ts), '-c', 'copy', '-y', T + '/v.mp4'])
# 3) audio: mix.wav's opening up to the first keep end is identical (stinger + welcome); the rest of the intro from dlg48
mix = rd(W + '/mix.wav'); dlg = rd(W + '/dlg48.wav')
if dlg.shape[1] == 1: dlg = np.repeat(dlg, 2, 1)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
run(['-i', old, '-vn', '-ac', '2', '-ar', str(SR), '-y', T + '/old.wav']); oa = rd(T + '/old.wav')
# The old mix's intro may have different cuts, so only its music is reused: music = mix - dialogue over the old
# intro's first piece (dialogue is placed at gain 1.0 in the mix), which holds the whole stinger.
old_first = float(os.environ.get('SAB_OLD_FIRST', '0')) or (keep[0][1] - keep[0][0])
nm = int(round(min(old_first, keep[0][1] - keep[0][0]) * SR)); a0 = int(round(keep[0][0] * SR))
music = mix[:nm] - dlg[a0:a0 + nm]
ref = slice(int(0.5 * SR), nm - int(0.2 * SR))
g = float(np.sqrt((oa[ref] ** 2).mean() / max(1e-9, (mix[ref] ** 2).mean())))      # loudnorm ran in linear mode: one gain
dlg = duck(dlg, edl)   # the adult's short reply lowered, not cut
parts = [dlg[int(round(x * SR)):int(round(y * SR))] for x, y in keep]
f = int(0.01 * SR); r = np.linspace(0, 1, f)[:, None]
for i in range(len(parts) - 1): parts[i] = parts[i].copy(); parts[i][-f:] *= r[::-1]; parts[i + 1] = parts[i + 1].copy(); parts[i + 1][:f] *= r
body = np.concatenate(parts); body[:len(music)] += music
intro_a = body * g; ni = int(round(new_intro * SR))
intro_a = np.pad(intro_a, ((0, max(0, ni - len(intro_a))), (0, 0)))[:ni]
# same limiter as the full mix (the delivered audio already went through it; the new intro hasn't)
w = wave.open(T + '/i.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.clip(intro_a, -32768, 32767).astype(np.int16).tobytes()); w.close()
run(['-i', T + '/i.wav', '-af', 'alimiter=limit=0.75:level=false', '-ar', str(SR), '-y', T + '/il.wav']); intro_a = rd(T + '/il.wav')[:ni]
out = np.concatenate([intro_a, oa[int(round(old_intro * SR)):]])
w = wave.open(T + '/n.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(np.clip(out, -32768, 32767).astype(np.int16).tobytes()); w.close()
run(['-i', T + '/v.mp4', '-i', T + '/n.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-y', new])
for p in os.listdir(T): os.remove(os.path.join(T, p))
os.rmdir(T); print('gain %.3f' % g, 'new intro %.3f s (was %.3f)' % (new_intro, old_intro), subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,duration', '-of', 'csv=p=0', new]).decode().split())
