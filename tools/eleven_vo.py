"""Josh's cloned-voice voiceover via ElevenLabs. Runs in the cloud container (the Mac VM's network can't reach api.elevenlabs.io).
usage: eleven_vo.py <secrets.env> <voice_sample.wav> <script.txt> <out.mp3> [voice_id_cache.json]
Clones the voice once from the sample (clean teaching clips from the episodes) and caches the voice id; then renders the script.
Copy out.mp3 to ~/sab/eps/<slug>/shorts/vo.wav (convert) before running sab_shorts.py <slug> facts."""
import sys, os, re, json, uuid, urllib.request

env, sample, script, out = sys.argv[1:5]
cache = sys.argv[5] if len(sys.argv) > 5 else os.path.join(os.path.dirname(env), 'elevenlabs_voice.json')
KEY = re.search(r'ELEVENLABS_API_KEY\s*=\s*(\S+)', open(env).read()).group(1).strip('"\'')
API = 'https://api.elevenlabs.io'


def call(path, data, ctype):
    req = urllib.request.Request(API + path, data=data, headers={'xi-api-key': KEY, 'Content-Type': ctype})
    try:
        return urllib.request.urlopen(req, timeout=300).read()
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code}: {e.read()[:400].decode(errors="replace")}')


if os.path.exists(cache):
    vid = json.load(open(cache))['voice_id']
else:
    b = '----sab' + uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="name"\r\n\r\nJosh (Super Art Bros)\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="remove_background_noise"\r\n\r\ntrue\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="files"; filename="{os.path.basename(sample)}"\r\nContent-Type: audio/mpeg\r\n\r\n').encode() \
        + open(sample, 'rb').read() + f'\r\n--{b}--\r\n'.encode()
    vid = json.loads(call('/v1/voices/add', body, 'multipart/form-data; boundary=' + b))['voice_id']
    json.dump({'voice_id': vid}, open(cache, 'w'))
    print('cloned voice', vid)

body = json.dumps({'text': open(script).read().strip(), 'model_id': os.environ.get('SAB_ELEVEN_MODEL', 'eleven_multilingual_v2'),
                   'voice_settings': {'stability': 0.4, 'similarity_boost': 0.85, 'style': 0.35, 'use_speaker_boost': True}}).encode()
open(out, 'wb').write(call(f'/v1/text-to-speech/{vid}?output_format=mp3_44100_128', body, 'application/json'))
print('wrote', out)
