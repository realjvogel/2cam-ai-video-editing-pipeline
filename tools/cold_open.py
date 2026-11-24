"""Cold open: a few seconds of the finished drawings (overhead camera) before the welcome, with a line of real dialogue over it.
usage: cold_open.py <slug> <frame_t> <dur> <audio_t0> <crop_x,crop_y,crop_w> [final.mp4] [out.mp4]
  frame_t: overhead (top) second of a clean, hands-free frame of both finished drawings; it is held as a still with a slow push-in.
  audio_t0: overhead second where the line starts; <dur> must cover the whole line (it should end before dur - 0.6).
  crop: normalised 16:9 box (x, y, width) on the overhead frame; centre the two drawings in it.
Ends with the same hard diagonal swipe as the intro (sab_wipe: thin cream edge, 0.5 s) into the episode's first frame.
Writes W/cold.mp4 and W/final_cold.mp4 (default). Chapters after 0:00 shift by <dur> seconds.
Runs on the VM (needs W/prep.json, W/dlg48.wav, the final)."""
import os, sys, json, subprocess
import numpy as np, cv2
slug, ft, dur, a0 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
cx, cy, cw = (float(v) for v in sys.argv[5].split(','))
W = os.path.join(os.path.expanduser(os.environ.get('SAB_WORK', '~/sab/eps')), slug)
final = sys.argv[6] if len(sys.argv) > 6 else W + '/final.mp4'; out = sys.argv[7] if len(sys.argv) > 7 else W + '/final_cold.mp4'
prep = json.load(open(W + '/prep.json')); SW, SH = prep.get('src_w', 3840), prep.get('src_h', 2160)
def run(a): subprocess.run(['ffmpeg', '-nostdin', '-v', 'error'] + a, check=True)
pw = int(cw * SW) // 2 * 2; ph = int(pw * 9 / 16) // 2 * 2; px = int(min(max(cx * SW, 0), SW - pw)) // 2 * 2; py = int(min(max(cy * SH, 0), SH - ph)) // 2 * 2
FPS, SWIPE, OW, OH = 24, 0.5, 1920, 1080
run(['-ss', str(ft), '-i', prep['top'], '-frames:v', '1', '-vf', f'crop={pw}:{ph}:{px}:{py},scale={OW * 2}:{OH * 2}:flags=lanczos', '-y', W + '/cold_still.png'])
run(['-i', final, '-frames:v', '1', '-y', W + '/cold_next.png'])                  # the welcome's first frame, revealed by the swipe
still = cv2.imread(W + '/cold_still.png'); nxt = cv2.imread(W + '/cold_next.png').astype(np.float32)
N = int(round(dur * FPS)); NS = int(round(SWIPE * FPS))
yy, xx = np.mgrid[0:OH, 0:OW].astype(np.float32); diag = (xx / OW + yy / OH) / 2   # 0 at top-left, 1 at bottom-right
cream = np.array([200, 226, 240], np.float32); ew = 0.006
enc = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{OW}x{OH}', '-r', str(FPS), '-i', '-',
                        '-ss', str(a0), '-t', str(dur), '-i', W + '/dlg48.wav',
                        '-af', f"afade=t=in:d=0.05,afade=t=out:st={dur - 0.25}:d=0.25,loudnorm=I=-15:TP=-2:LRA=11",
                        '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-profile:v', 'high', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-video_track_timescale', '12288', '-t', str(dur), '-y', W + '/cold.mp4'],
                       stdin=subprocess.PIPE)
H2, W2 = still.shape[:2]
for k in range(N):
    z = 1 + 0.05 * k / max(1, N - 1)                                             # slow 5% push-in, centred
    cw2, ch2 = W2 / z, H2 / z; x0, y0 = (W2 - cw2) / 2, (H2 - ch2) / 2
    a = cv2.resize(still[int(y0):int(y0 + ch2), int(x0):int(x0 + cw2)], (OW, OH), interpolation=cv2.INTER_AREA).astype(np.float32)
    j = k - (N - NS)
    if j >= 0:                                                                   # hard diagonal swipe, top-left -> bottom-right
        p = j / max(1, NS - 1); p = p * p * (3 - 2 * p); e = -0.05 + 1.1 * p
        m = (diag < e)[..., None]; line = (np.abs(diag - e) < ew)[..., None]
        a = np.where(line, cream, np.where(m, nxt, a))
    enc.stdin.write(np.clip(a, 0, 255).astype(np.uint8).tobytes())
enc.stdin.close(); enc.wait()
open(W + '/cold_list.txt', 'w').write(f"file '{W}/cold.mp4'\nfile '{final}'\n")
run(['-f', 'concat', '-safe', '0', '-i', W + '/cold_list.txt', '-c', 'copy', '-movflags', '+faststart', '-y', out])
print('cold open', dur, 's ->', out)
