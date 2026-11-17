"""YouTube Data API helper for the Super Art Bros channel (standard library only).

Video files are uploaded in YouTube Studio: uploads from an unaudited API project are locked to Private
for good. Everything after the upload goes through here: thumbnails, titles/descriptions, made-for-kids,
privacy and publish schedules.

Credentials (both gitignored, never committed, live in SAB-production/ on the SSD):
  youtube_client_secret.json   OAuth "Desktop app" client from Google Cloud project super-art-bros-publishing
  youtube_token.json           written by `auth-code`; holds the refresh token

usage:
  sab_youtube.py auth-url                         print the consent URL (open it, approve, copy the URL you land on)
  sab_youtube.py auth-code '<redirect URL>'       exchange the code from that URL for a token
  sab_youtube.py list                             every video on the channel: id, privacy, publishAt, title
  sab_youtube.py thumb <videoId> <image.jpg>      set the custom thumbnail (jpg/png, <= 2 MB)
  sab_youtube.py update <videoId> [--title T] [--desc-file F] [--kids] [--private] [--publish-at 2026-12-05T14:00:00Z]
  sab_youtube.py match '<text>'                   video ids whose title contains text (case-insensitive)
"""
import json, os, sys, time, urllib.parse, urllib.request, urllib.error

ROOT = os.path.join(os.path.expanduser(os.environ.get('SAB_SSD', '~/sab-data')), 'SAB-production')
SECRET = os.environ.get('SAB_YT_SECRET', os.path.join(ROOT, 'youtube_client_secret.json'))
TOKEN = os.environ.get('SAB_YT_TOKEN', os.path.join(ROOT, 'youtube_token.json'))
SCOPE = 'https://www.googleapis.com/auth/youtube'
REDIRECT = 'http://127.0.0.1:8765'
API = 'https://www.googleapis.com/youtube/v3'
CHANNEL = os.environ.get('SAB_YT_CHANNEL', '<your channel id>')   # Super Art Bros; the token must belong to this channel

def client():
    c = json.load(open(SECRET)); return c.get('installed') or c.get('web')

def http(method, url, data=None, headers=None, raw=False):
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            b = r.read(); return b if raw else (json.loads(b) if b else {})
    except urllib.error.HTTPError as e:
        sys.exit(f'HTTP {e.code} {method} {url.split("?")[0]}: {e.read().decode()[:600]}')

def save_token(t):
    old = json.load(open(TOKEN)) if os.path.exists(TOKEN) else {}
    old.update(t); old['expires_at'] = time.time() + t.get('expires_in', 3600) - 60
    with open(TOKEN, 'w') as f: json.dump(old, f); f.flush(); os.fsync(f.fileno())
    for _ in range(20):   # the SSD is exFAT and can take a moment before a fresh file is visible
        if os.path.exists(TOKEN): break
        time.sleep(0.5)
    try: os.chmod(TOKEN, 0o600)
    except OSError: pass

def access_token():
    for _ in range(20):
        if os.path.exists(TOKEN): break
        time.sleep(0.5)
    if not os.path.exists(TOKEN): sys.exit('no token yet: run auth-url, then auth-code')
    t = json.load(open(TOKEN))
    if 'refresh_token' not in t: sys.exit('no token yet: run auth-url, then auth-code')
    if time.time() < t.get('expires_at', 0): return t['access_token']
    c = client()
    body = urllib.parse.urlencode(dict(client_id=c['client_id'], client_secret=c['client_secret'],
                                       refresh_token=t['refresh_token'], grant_type='refresh_token')).encode()
    save_token(http('POST', c['token_uri'], body, {'Content-Type': 'application/x-www-form-urlencoded'}))
    return json.load(open(TOKEN))['access_token']

def api(method, path, params=None, body=None):
    url = f'{API}/{path}?' + urllib.parse.urlencode(params or {})
    h = {'Authorization': 'Bearer ' + access_token()}
    if body is not None: h['Content-Type'] = 'application/json'; body = json.dumps(body).encode()
    return http(method, url, body, h)

def all_videos():
    ch = api('GET', 'channels', {'part': 'contentDetails', 'mine': 'true'})['items'][0]
    if ch['id'] != CHANNEL: sys.exit(f"token is for channel {ch['id']}, not Super Art Bros: run auth-url / auth-code again")
    up = ch['contentDetails']['relatedPlaylists']['uploads']; ids = []; tok = None
    while True:
        p = {'part': 'contentDetails', 'playlistId': up, 'maxResults': 50}
        if tok: p['pageToken'] = tok
        r = api('GET', 'playlistItems', p); ids += [i['contentDetails']['videoId'] for i in r['items']]
        tok = r.get('nextPageToken')
        if not tok: break
    out = []
    for k in range(0, len(ids), 50):
        out += api('GET', 'videos', {'part': 'snippet,status,contentDetails', 'id': ','.join(ids[k:k + 50])})['items']
    return out

def main(a):
    cmd = a[0] if a else 'help'
    if cmd == 'auth-url':
        c = client()
        print(c['auth_uri'] + '?' + urllib.parse.urlencode(dict(client_id=c['client_id'], redirect_uri=REDIRECT, response_type='code',
              scope=SCOPE, access_type='offline', prompt='select_account consent')))   # always show the account/channel picker
    elif cmd == 'auth-code':
        q = urllib.parse.parse_qs(urllib.parse.urlparse(a[1]).query); code = q.get('code', [a[1]])[0]; c = client()
        body = urllib.parse.urlencode(dict(code=code, client_id=c['client_id'], client_secret=c['client_secret'],
                                           redirect_uri=REDIRECT, grant_type='authorization_code')).encode()
        save_token(http('POST', c['token_uri'], body, {'Content-Type': 'application/x-www-form-urlencoded'}))
        ch = api('GET', 'channels', {'part': 'snippet', 'mine': 'true'})['items'][0]
        if ch['id'] != CHANNEL:
            open(TOKEN, 'w').write('{}')   # blank it (files can't be deleted on the SSD from the device shell)
            sys.exit(f"approved for '{ch['snippet']['title']}' ({ch['id']}), not the Super Art Bros channel: token discarded. "
                     "Run auth-url again and pick the Super Art Bros channel when Google asks which account/channel to use.")
        print('authorised for channel:', ch['snippet']['title'])
    elif cmd in ('list', 'match'):
        for v in all_videos():
            s = v['status']; t = v['snippet']['title']
            if cmd == 'match' and a[1].lower() not in t.lower(): continue
            print(v['id'], s['privacyStatus'], s.get('publishAt', '-'), s.get('madeForKids'), v['contentDetails']['duration'], t, sep=' | ')
    elif cmd == 'thumb':
        vid, img = a[1], a[2]; data = open(img, 'rb').read()
        if len(data) > 2 * 1024 * 1024: sys.exit('thumbnail over 2 MB')
        url = 'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?' + urllib.parse.urlencode({'videoId': vid, 'uploadType': 'media'})
        r = http('POST', url, data, {'Authorization': 'Bearer ' + access_token(),
                                     'Content-Type': 'image/png' if img.lower().endswith('.png') else 'image/jpeg'})
        print('thumbnail set', vid, r['items'][0]['default']['url'] if r.get('items') else '')
    elif cmd == 'update':
        vid = a[1]; v = api('GET', 'videos', {'part': 'snippet,status', 'id': vid})['items'][0]
        sn = {k: v['snippet'][k] for k in ('title', 'description', 'categoryId', 'tags', 'defaultLanguage') if k in v['snippet']}
        st = {k: v['status'][k] for k in ('privacyStatus', 'publishAt', 'embeddable', 'license', 'publicStatsViewable') if k in v['status']}
        st['selfDeclaredMadeForKids'] = v['status'].get('madeForKids', True)
        i = 2
        while i < len(a):
            o = a[i]
            if o == '--title': sn['title'] = a[i + 1]; i += 2
            elif o == '--desc-file': sn['description'] = open(a[i + 1]).read().strip(); i += 2
            elif o == '--kids': st['selfDeclaredMadeForKids'] = True; i += 1
            elif o == '--private': st['privacyStatus'] = 'private'; st.pop('publishAt', None); i += 1
            elif o == '--publish-at': st['privacyStatus'] = 'private'; st['publishAt'] = a[i + 1]; i += 2   # scheduled: private until then
            else: sys.exit('unknown option ' + o)
        r = api('PUT', 'videos', {'part': 'snippet,status'}, {'id': vid, 'snippet': sn, 'status': st})
        print('updated', vid, r['status']['privacyStatus'], r['status'].get('publishAt', '-'), r['snippet']['title'])
    else:
        print(__doc__)

if __name__ == '__main__':
    main(sys.argv[1:])
