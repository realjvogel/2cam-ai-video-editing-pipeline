"""Export an episode as a DaVinci Resolve timeline (FCPXML 1.9), for small hand tweaks.
usage: resolve_export.py <slug> <final.mp4 on the Mac> <out.fcpxml> [cold_open_seconds]
  The timeline is the finished episode, cut at every real edit point of the pipeline (cold open, intro, swipe, each lesson
  stretch between cuts, cutaways, sped-up coloring, review, goodbye, iris, end screen), one clip per piece, named by section
  and raw-camera time. Trim, delete or reorder clips; extending a clip shows the neighbouring piece (the finished file has no
  extra footage past each cut), so ask for a re-render when a cut needs more room.
  The raw camera files (overhead + front) are added to the media pool, for dropping in other shots.
  Paths are written as the Mac sees them (<SAB_SSD>/...), so Resolve finds the media directly.
Runs on the VM (reads W/edl.json, W/groups.json and the rendered pieces in W/vo to get each piece's length)."""
import os, sys, json, subprocess, urllib.parse
from fractions import Fraction
slug, final_mac, out = sys.argv[1], sys.argv[2], sys.argv[3]; cold = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
W = os.path.join(os.path.expanduser(os.environ.get('SAB_WORK', '~/sab/eps')), slug)
SSD_VM = os.path.expanduser(os.environ.get('SAB_SSD', '~/sab-data')); SSD_MAC = os.environ.get('SAB_SSD_MAC', '<SAB_SSD>')
edl = json.load(open(W + '/edl.json')); groups = json.load(open(W + '/groups.json')); prep = json.load(open(W + '/prep.json'))
segs = {s['name']: s for s in edl['segments']}
FPS = 24
def dur(p): return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p]))
def fr(t): return round(t * FPS)                       # seconds -> whole frames
def ts(n): return f"{Fraction(n, FPS).numerator}/{Fraction(n, FPS).denominator}s" if n % FPS else f"{n // FPS}s"
def mac(p):                                            # VM path -> Mac path, as a file:// URL
    if p.startswith(SSD_VM): p = SSD_MAC + p[len(SSD_VM):]
    return 'file://' + urllib.parse.quote(p)
LABEL = dict(intro='Intro', wipe='Swipe', draw='Drawing', cutaway='Cutaway (front cam)', to_color='Time to color', color_ask='Time to color',
             montage='Coloring (sped up)', review='Review', bye='Goodbye', iris='Iris', outro_video='End screen')
# pieces in timeline order, merging neighbours that are one continuous stretch of the same raw footage
pieces = [['Cold open', None, None, cold]] if cold else []
for _, files in groups:
    for f in files:
        name = os.path.basename(f)[:-4]; s = segs.get(name, {'role': name.rstrip('0123456789'), 'a': 0, 'b': 0}); d = dur(W + '/vo/' + name + '.mp4')
        lab = LABEL.get(s['role'], s['role']); p = pieces[-1] if pieces else None
        if p and p[0] == lab and p[2] is not None and abs(p[2] - s['a']) < 0.05 and s['role'] not in ('intro', 'wipe', 'iris', 'outro_video'):
            p[2] = s['b']; p[3] += d
        else: pieces.append([lab, s['a'], s['b'], d])
total = dur(final_mac.replace(SSD_MAC, SSD_VM)) if final_mac.startswith(SSD_MAC) else sum(p[3] for p in pieces)
spine, t = [], 0
for i, (lab, a, b, d) in enumerate(pieces):
    n0, n1 = fr(t), fr(t + d) if i < len(pieces) - 1 else fr(total)
    nm = lab if a is None or lab in ('Swipe', 'Iris', 'End screen') else f"{lab} (raw {int(a // 60)}:{a % 60:04.1f})"
    spine.append(f'        <asset-clip ref="r2" offset="{ts(n0)}" name="{nm}" start="{ts(n0)}" duration="{ts(n1 - n0)}" format="r1" tcFormat="NDF"/>')
    t += d
fronts = [l.split(' ', 1)[1] for l in open(prep['front']).read().splitlines() if l.startswith('file ')] if prep['front'].endswith('.ffconcat') else [prep['front']]
fronts = [p for p in fronts if 'gap' not in os.path.basename(p)]          # the black filler between two camera clips isn't media
raws = [('Overhead camera', prep['top'])] + [(f'Front camera {i + 1}' if len(fronts) > 1 else 'Front camera', p) for i, p in enumerate(fronts)]
assets, clips = [], []
for k, (nm, p) in enumerate(raws):
    p = os.path.realpath(os.path.join(os.path.dirname(prep['front']), p)) if not p.startswith('/') else p
    d = fr(dur(p)); rid = f'r{10 + k}'
    assets.append(f'    <asset id="{rid}" name="{nm}" start="0s" duration="{ts(d)}" hasVideo="1" hasAudio="1" audioSources="1" audioChannels="2" audioRate="48000">\n'
                  f'      <media-rep kind="original-media" src="{mac(p)}"/>\n    </asset>')
    clips.append(f'    <asset-clip ref="{rid}" name="{nm}" duration="{ts(d)}"/>')
title = os.path.basename(final_mac)[:-4]
xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.9">
  <resources>
    <format id="r1" name="FFVideoFormat1080p24" frameDuration="1/24s" width="1920" height="1080"/>
    <asset id="r2" name="{title}" start="0s" duration="{ts(fr(total))}" hasVideo="1" format="r1" hasAudio="1" audioSources="1" audioChannels="2" audioRate="48000">
      <media-rep kind="original-media" src="{mac(final_mac)}"/>
    </asset>
{chr(10).join(assets)}
  </resources>
  <library>
    <event name="Super Art Bros - {slug}">
{chr(10).join(clips)}
      <project name="{title}">
        <sequence format="r1" duration="{ts(fr(total))}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
{chr(10).join(spine)}
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
'''
open(out, 'w').write(xml)
print(len(pieces), 'clips,', round(total, 2), 's ->', out)
for lab, a, b, d in pieces: print(f'  {d:7.2f}s  {lab}' + (f'  raw {a:.1f}-{b:.1f}' if a is not None else ''))
