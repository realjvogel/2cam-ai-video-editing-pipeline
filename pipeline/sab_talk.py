"""Flag lines that shouldn't reach the viewer: talk aimed at the editor or the camera, and retakes.
usage: python3 sab_talk.py <transcript.json> <edl.json>
transcript: [{s, e, t}, ...] in raw overhead seconds (faster-whisper segments).
Prints each flagged line that falls inside a kept (non-montage) segment, with its raw time, so it can be
added to episode.json `skips` or the beat edges moved. Exit code 1 when anything is flagged."""
import json, re, sys

EDITOR = re.compile(r"\b(transition|cue the music|fast[- ]?motion|speed (it|this) up|in the edit|edit (this|that) out|cut (this|that) out|"
                    r"we('ll| will) cut|testing|check,? check|recording|is it recording|is that on|"
                    r"should we call it|are we done|we done\??$|say (that|it) again|one more time|let'?s (redo|do that again|start over)|start over|"
                    r"look right there|look at the camera|look at me|say,? okay|take two|retake)\b", re.I)

def norm(t): return re.sub(r"[^a-z' ]", "", t.lower()).split()

def main(tp, ep):
    T = json.load(open(tp)); E = json.load(open(ep))
    keep = [(s['a'], s['b'], s['name']) for s in E['segments'] if s['role'] not in ('montage', 'outro_video', 'wipe', 'iris')]
    def where(a, b):
        for x, y, n in keep:
            if a < y and b > x: return n
    flags = []
    for i, seg in enumerate(T):
        n = where(seg['s'], seg['e'])
        if not n: continue
        if EDITOR.search(seg['t']): flags.append((seg['s'], seg['e'], n, 'editor/camera talk', seg['t'].strip()))
        # retake: the same 6+ word run said again within 20 s (shorter runs are normal teaching repetition)
        w = norm(seg['t'])
        for later in T[i + 1:]:
            if later['s'] - seg['e'] > 20: break
            v = norm(later['t']); sv = ' '.join(v)
            if any(' '.join(w[k:k + 6]) in sv for k in range(max(0, len(w) - 5))) and len(w) >= 6 and where(later['s'], later['e']):
                flags.append((seg['s'], later['e'], n, 'retake', seg['t'].strip() + '  ||  ' + later['t'].strip())); break
    for a, b, n, k, t in flags:
        print(f"{a:8.2f}-{b:8.2f}  {n:12s} {k:20s} {t[:160]}")
    return 1 if flags else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
