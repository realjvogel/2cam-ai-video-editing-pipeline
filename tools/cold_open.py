"""Cold open: a few seconds of the finished drawings (overhead camera) before the welcome, with a line of real dialogue over it.
usage: cold_open.py <slug> <video_t0> <dur> <audio_t0> <crop_x,crop_y,crop_w> [final.mp4] [out.mp4]
  video_t0 / audio_t0: overhead (top) seconds. The picture and the line can come from different moments, e.g. a hands-free shot
  of both finished drawings under "Man, that is an awesome dragon". crop: normalised 16:9 box (x, y, width) on the overhead frame.
Writes W/cold.mp4 and prepends it to the final (default W/final.mp4 -> W/final_cold.mp4). Chapters shift by <dur> seconds.
Runs on the VM (needs W/prep.json, W/dlg48.wav)."""
import os, sys, json, subprocess
slug, v0, dur, a0 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
cx, cy, cw = (float(v) for v in sys.argv[5].split(','))
W = os.path.join(os.path.expanduser(os.environ.get('SAB_WORK', '~/sab/eps')), slug)
final = sys.argv[6] if len(sys.argv) > 6 else W + '/final.mp4'; out = sys.argv[7] if len(sys.argv) > 7 else W + '/final_cold.mp4'
prep = json.load(open(W + '/prep.json')); SW, SH = prep.get('src_w', 3840), prep.get('src_h', 2160)
def run(a): subprocess.run(['ffmpeg', '-nostdin', '-v', 'error'] + a, check=True)
pw = int(cw * SW) // 2 * 2; ph = int(pw * 9 / 16) // 2 * 2; px = int(min(max(cx * SW, 0), SW - pw)) // 2 * 2; py = int(min(max(cy * SH, 0), SH - ph)) // 2 * 2
# slow push-in (4%) over the clip, then a quick white flash into the welcome
zoom = f"scale=w='iw*(1+0.04*t/{dur})':h='ih*(1+0.04*t/{dur})':eval=frame,crop=1920:1080"
vf = f"crop={pw}:{ph}:{px}:{py},scale=1920:1080:flags=lanczos,fps=24,{zoom},fade=t=out:st={dur - 0.2}:d=0.2:color=white,format=yuv420p"
af = f"afade=t=in:d=0.05,afade=t=out:st={dur - 0.3}:d=0.3,loudnorm=I=-15:TP=-2:LRA=11"
run(['-ss', str(v0), '-t', str(dur), '-i', prep['top'], '-ss', str(a0), '-t', str(dur), '-i', W + '/dlg48.wav',
     '-map', '0:v', '-map', '1:a', '-vf', vf, '-af', af, '-r', '24', '-c:v', 'libx264', '-profile:v', 'high', '-preset', 'veryfast', '-crf', '17',
     '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-video_track_timescale', '12288', '-t', str(dur), '-y', W + '/cold.mp4'])
open(W + '/cold_list.txt', 'w').write(f"file '{W}/cold.mp4'\nfile '{final}'\n")
run(['-f', 'concat', '-safe', '0', '-i', W + '/cold_list.txt', '-c', 'copy', '-movflags', '+faststart', '-y', out])
print('cold open', dur, 's ->', out)
