import hashlib
import gzip
import hmac
import http.cookies
import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import time
import zlib
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, unquote

from . import innertube, comments
from .media import start_worker
from .store import DATA, db, init, video, videos

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = os.environ.get('PUBLIC_ORIGIN', 'http://localhost:3000').rstrip('/')
MAX_UPLOAD = int(os.environ.get('MAX_UPLOAD_MB', '500')) * 1024 * 1024
ID = r'[A-Za-z0-9_-]{11}'
RATE = OrderedDict()
import threading
RATE_LOCK = threading.Lock()
TELEMETRY_PATHS = frozenset(('/api/stats/qoe', '/api/stats/playback', '/api/stats/atr',
                             '/api/stats/watchtime', '/generate_204'))


class Error(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def uid():
    return secrets.token_urlsafe(8)


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ':' + digest


def public(row):
    if row is None:
        raise Error(404, 'Not found')
    return dict(row)


class Handler(BaseHTTPRequestHandler):
    server_version = 'MewTube/0.1'
    protocol_version = 'HTTP/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(60)

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        # Client archives are intentionally sandboxed to this origin as well.
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; font-src 'self' data:; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'")
        super().end_headers()

    def send(self, body, status=200, headers=None, content_type='application/json; charset=utf-8'):
        raw = json.dumps(body).encode() if content_type.startswith('application/json') else body
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def json_body(self):
        maximum = 1024 * 1024
        length = self.length(maximum)
        raw = self.rfile.read(length)
        encoding = self.headers.get('Content-Encoding', 'identity').strip().lower()
        if encoding not in ('identity', 'gzip'):
            raise Error(415, 'Unsupported content encoding')
        try:
            if encoding == 'gzip':
                # The current official transport compresses InnerTube JSON.
                # Bound decoded bytes too; gzip.decompress() is unbounded.
                with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                    raw = stream.read(maximum + 1)
                if len(raw) > maximum:
                    raise Error(413, 'Decoded request is too large')
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError()
            for key in ('username', 'password', 'title', 'description', 'text', 'reason', 'channelId', 'videoId', 'query', 'browseId', 'continuation'):
                if key in value and not isinstance(value[key], str):
                    raise ValueError()
            if 'enabled' in value and not isinstance(value['enabled'], bool):
                raise ValueError()
            return value
        except (ValueError, RecursionError, OSError, EOFError, zlib.error):
            raise Error(400, 'Expected a JSON object')

    def length(self, maximum):
        if self.headers.get('Transfer-Encoding'):
            raise Error(400, 'Chunked requests are not supported')
        try:
            n = int(self.headers['Content-Length'])
        except (ValueError, TypeError):
            raise Error(411, 'Content-Length is required')
        if not 0 <= n <= maximum:
            raise Error(413, 'Request is too large')
        return n

    def user(self, c, required=False):
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            raw = cookie['session'].value if 'session' in cookie else ''
        except http.cookies.CookieError:
            raw = ''
        row = c.execute('''SELECT u.id,u.username,u.admin FROM users u JOIN sessions s ON s.user_id=u.id
                         WHERE s.token=? AND s.expires>?''', (hashlib.sha256(raw.encode()).hexdigest(), int(time.time()))).fetchone()
        if required and not row:
            raise Error(401, 'Sign in first')
        return row

    def limit(self, kind, cap):
        key = (self.client_address[0], kind)
        now = time.monotonic()
        with RATE_LOCK:
            count, start = RATE.pop(key, (0, now))
            if now - start > 60:
                count, start = 0, now
            RATE[key] = (count + 1, start)
            while len(RATE) > 10000:
                RATE.popitem(last=False)
        if count >= cap:
            raise Error(429, 'Too many requests; try again in a minute')

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def dispatch(self):
        try:
            self.route()
        except Error as e:
            self.send({'error': e.message}, e.status)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception as e:
            # Deliberately log the type only, never uploaded content or passwords.
            print('Request failed:', type(e).__name__, flush=True)
            self.send({'error': 'Internal server error'}, 500)

    def route(self):
        url = urlsplit(self.path)
        path, query = url.path, parse_qs(url.query)
        if len(self.path) > 4096:
            raise Error(414, 'URL too long')
        if self.command == 'POST':
            if self.headers.get('Origin') not in (None, ORIGIN):
                raise Error(403, 'Origin rejected')
            if self.headers.get('X-MewTube') != '1':
                raise Error(403, 'X-MewTube header is required')
            if path not in TELEMETRY_PATHS and path != '/youtubei/v1/log_event':
                self.limit('write', 100)
        if path in TELEMETRY_PATHS or (path == '/youtubei/v1/log_event' and self.command == 'POST'):
            if self.command not in ('GET', 'HEAD', 'POST'):
                raise Error(405, 'Method not allowed')
            # Guest clients emit many analytics calls on every navigation.
            # Discard them without retaining queries/bodies or consuming the
            # local account/mutation budget. No upstream request is made.
            self.limit('telemetry', 600)
            if self.command == 'POST':
                self.rfile.read(self.length(1024 * 1024))
            if path == '/youtubei/v1/log_event':
                return self.send({'responseContext': {}})
            return self.send(b'', status=204, content_type='text/plain')
        if path == '/healthz':
            return self.send({'ok': True, 'ffmpeg': bool(shutil.which('ffmpeg'))})
        if path.startswith('/media/') and self.command in ('GET', 'HEAD'):
            match = re.fullmatch(r'/media/(' + ID + r')/(video\.mp4|thumb\.jpg)', path)
            if not match:
                raise Error(404, 'Not found')
            with db() as c:
                v = video(c, match[1])
                if not v or v['status'] != 'ready':
                    raise Error(404, 'Not found')
            return self.file(DATA / 'media' / match[1] / match[2])
        if path.startswith('/client-assets/') and self.command in ('GET', 'HEAD'):
            from .snapshot import asset_path
            return self.file(asset_path(path.removeprefix('/client-assets/')))
        if path.startswith(('/s/', '/client-static/')) and self.command in ('GET', 'HEAD'):
            from .snapshot import dynamic_asset
            # Cached immutable files do not consume the upstream-download quota.
            return self.file(dynamic_asset(path, ORIGIN, lambda: self.limit('client-assets', 240)))
        cookie = http.cookies.SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except http.cookies.CookieError:
            cookie = http.cookies.SimpleCookie()
        channel_path = re.fullmatch(r'/channel/(' + ID + ')', path)
        official = path == '/official' or (not (cookie.get('mewtube_client') and cookie['mewtube_client'].value == 'independent')
                    and (path in ('/', '/watch', '/results', '/feed/subscriptions', '/playlist') or channel_path)
                    and query.get('native') != ['1'] and query.get('signin') != ['1'])
        if official and self.command in ('GET', 'HEAD'):
            from .snapshot import shell
            watch_id = query.get('v', [None])[0] if path in ('/watch', '/official') else None
            if watch_id and not re.fullmatch(ID, watch_id):
                raise Error(400, 'Invalid video ID')
            with db() as c:
                if path == '/playlist' and query.get('list') != ['LL']:
                    raise Error(501, 'Only the local liked-videos playlist is currently supported')
                browse_id = channel_path[1] if channel_path else ('FEsubscriptions' if path == '/feed/subscriptions' else
                                                                 ('VLLL' if path == '/playlist' else ''))
                content = shell(c, ORIGIN, watch_id, query.get('search_query', [None])[0] if path == '/results' else None,
                                self.user(c), browse_id)
            if content is None:
                raise Error(503, 'Captured client page unavailable. Run python scripts/fetch_client.py --latest. Independent UI: /?native=1')
            return self.send(content, headers={'Set-Cookie':'mewtube_client=official; Path=/; SameSite=Lax; HttpOnly'}, content_type='text/html; charset=utf-8')
        if path.startswith('/youtubei/v1/') and self.command == 'POST':
            body = self.json_body()
            operation = path.removeprefix('/youtubei/v1/')
            with db() as c:
                if operation == 'account/account_menu':
                    user = self.user(c, True)
                    return self.send(innertube.account_menu(user))
                if operation == 'comment/create_comment':
                    user = self.user(c, True)
                    self.limit('comment', 20)
                    params, value = body.get('createCommentParams'), body.get('commentText')
                    target = re.fullmatch(re.escape(comments.CREATE_PREFIX) + '(' + ID + ')', params) if isinstance(params, str) else None
                    if not target or not isinstance(value, str) or not 1 <= len(value.strip()) <= 2000:
                        raise Error(400, 'Local comment target and 1–2000 characters are required')
                    v = video(c, target[1])
                    if not v or v['status'] != 'ready':
                        raise Error(404, 'Video not found')
                    comment_id = uid()
                    c.execute('INSERT INTO comments(id,user_id,video_id,text,created) VALUES(?,?,?,?,?)',
                              (comment_id, user['id'], v['id'], value.strip(), int(time.time())))
                    c.commit()
                    view, framework = comments.section(c, v, user, comment_id)
                    thread = view['itemSectionRenderer']['contents'][0]
                    return self.send({'responseContext': {}, 'frameworkUpdates': framework,
                                      'actions': [{'createCommentAction': {'contents': thread}}]})
                if operation in ('subscription/subscribe', 'subscription/unsubscribe'):
                    user = self.user(c, True)
                    channels = body.get('channelIds')
                    if (not isinstance(channels, list) or not 1 <= len(channels) <= 20 or
                            any(not isinstance(value, str) or not re.fullmatch(ID, value) for value in channels) or
                            len(set(channels)) != len(channels)):
                        raise Error(400, 'Expected 1–20 distinct local channel IDs')
                    for channel in channels:
                        if not c.execute('SELECT 1 FROM users WHERE id=?', (channel,)).fetchone():
                            raise Error(404, 'Channel not found')
                    for channel in channels:
                        if operation == 'subscription/subscribe':
                            c.execute('INSERT OR IGNORE INTO subscriptions VALUES(?,?)', (user['id'], channel))
                        else:
                            c.execute('DELETE FROM subscriptions WHERE user_id=? AND channel_id=?', (user['id'], channel))
                    c.commit()
                    return self.send({'responseContext': {}})
                if operation in ('like/like', 'like/removelike'):
                    user = self.user(c, True)
                    target = body.get('target')
                    video_id = target.get('videoId') if isinstance(target, dict) else None
                    if not isinstance(video_id, str) or not re.fullmatch(ID, video_id):
                        raise Error(400, 'Invalid like target')
                    v = video(c, video_id)
                    if not v or v['status'] != 'ready':
                        raise Error(404, 'Video not found')
                    if operation == 'like/like':
                        c.execute('INSERT OR IGNORE INTO likes VALUES(?,?)', (user['id'], video_id))
                    else:
                        c.execute('DELETE FROM likes WHERE user_id=? AND video_id=?', (user['id'], video_id))
                    c.commit()
                    return self.send({'responseContext': {}})
                result = innertube.response(c, operation, body, ORIGIN, self.user(c))
                if result is None:
                    c.execute('INSERT INTO unknown_calls(path) VALUES(?) ON CONFLICT(path) DO UPDATE SET count=count+1', (operation[:200],))
            if result is None:
                raise Error(501, 'Unsupported InnerTube operation')
            return self.send(result)
        if path.startswith('/api/'):
            return self.api(path, query)
        if self.command not in ('GET', 'HEAD'):
            raise Error(405, 'Method not allowed')
        assets = {'/app.js': 'app.js', '/auth-return.js': 'auth-return.js', '/style.css': 'style.css', '/bridge.js': 'bridge.js',
                  '/': 'index.html', '/watch': 'index.html', '/results': 'index.html', '/studio': 'index.html',
                  '/subscriptions': 'index.html', '/channel': 'index.html', '/admin': 'index.html'}
        if path not in assets:
            raise Error(404, 'Not found')
        if query.get('native') == ['1'] or query.get('signin') == ['1']:
            return self.send((ROOT / 'web' / assets[path]).read_bytes(),
                headers={'Set-Cookie':'mewtube_client=independent; Path=/; SameSite=Lax; HttpOnly'},
                content_type='text/html; charset=utf-8')
        return self.file(ROOT / 'web' / assets[path])

    def api(self, path, query):
        post = self.command == 'POST'
        with db() as c:
            u = self.user(c)
            if not post:
                if path == '/api/me':
                    return self.send({'user': dict(u) if u else None})
                if path == '/api/videos':
                    if query.get('feed') == ['subscriptions'] and not u:
                        raise Error(401, 'Sign in first')
                    page = min(10000, max(0, int(query.get('page', ['0'])[0]))) if query.get('page', ['0'])[0].isdigit() else 0
                    rows = videos(c, query.get('q', [''])[0][:200], query.get('channel', [None])[0],
                                  u['id'] if u and query.get('feed') == ['subscriptions'] else None, offset=page * 40)
                    return self.send({'videos': [dict(v) for v in rows], 'page': page})
                if path == '/api/studio':
                    u = self.user(c, True)
                    rows = c.execute('SELECT * FROM videos WHERE owner=? ORDER BY created DESC', (u['id'],)).fetchall()
                    return self.send({'videos': [dict(v) for v in rows]})
                if path == '/api/admin':
                    if not u or not u['admin']:
                        raise Error(403, 'Operator access required')
                    return self.send({'reports': [dict(r) for r in c.execute('SELECT * FROM reports ORDER BY created DESC LIMIT 100')],
                                      'unknown': [dict(r) for r in c.execute('SELECT * FROM unknown_calls ORDER BY count DESC LIMIT 100')]})
                match = re.fullmatch(r'/api/videos/(' + ID + ')', path)
                if match:
                    v = public(video(c, match[1]))
                    if v['status'] != 'ready' and (not u or (v['owner'] != u['id'] and not u['admin'])):
                        raise Error(404, 'Not found')
                    v['liked'] = bool(u and c.execute('SELECT 1 FROM likes WHERE user_id=? AND video_id=?', (u['id'], v['id'])).fetchone())
                    v['subscribed'] = bool(u and c.execute('SELECT 1 FROM subscriptions WHERE user_id=? AND channel_id=?', (u['id'], v['owner'])).fetchone())
                    comments = c.execute('''SELECT co.id,co.text,co.created,u.username FROM comments co
                                           JOIN users u ON u.id=co.user_id WHERE video_id=? ORDER BY co.created DESC LIMIT 100''', (v['id'],)).fetchall()
                    return self.send({'video': v, 'comments': [dict(r) for r in comments]})
                raise Error(404, 'Not found')
        # Mutations use fresh transactions so streaming uploads do not lock the DB.
        if path in ('/api/register', '/api/login'):
            self.limit('auth', 10)
            body = self.json_body()
            name, password = body.get('username', ''), body.get('password', '')
            if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_]{3,24}', name):
                raise Error(400, 'Username must be 3–24 letters, numbers, or underscores')
            if not isinstance(password, str) or not 10 <= len(password) <= 200:
                raise Error(400, 'Password must be 10–200 characters')
            with db() as c:
                if path == '/api/register':
                    if os.environ.get('SIGNUPS', '1') != '1':
                        raise Error(403, 'Signups are disabled')
                    try:
                        c.execute('INSERT INTO users(id,username,password) VALUES(?,?,?)', (uid(), name, password_hash(password)))
                    except sqlite3.IntegrityError:
                        raise Error(409, 'Username unavailable')
                user = c.execute('SELECT * FROM users WHERE username=?', (name,)).fetchone()
                stored = user['password'] if user else password_hash('dummy-account-password')
                if not hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored) or not user:
                    raise Error(401, 'Invalid username or password')
                token = secrets.token_urlsafe(32)
                c.execute('DELETE FROM sessions WHERE expires<=?', (int(time.time()),))
                c.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), user['id'], int(time.time()) + 604800))
                c.commit()
                secure = '; Secure' if ORIGIN.startswith('https://') else ''
                return self.send({'user': {k: user[k] for k in ('id', 'username', 'admin')}}, headers={
                    'Set-Cookie': f'session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800{secure}'})
        with db() as c:
            u = self.user(c, True)
        if path == '/api/upload':
            self.limit('upload', 10)
            return self.upload(u)
        body = self.json_body()
        with db() as c:
            if path == '/api/logout':
                c.execute('DELETE FROM sessions WHERE user_id=?', (u['id'],))
                c.commit()
                return self.send({'ok': True}, headers={'Set-Cookie': 'session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax'})
            if path == '/api/subscribe':
                channel = body.get('channelId', '')
                if not c.execute('SELECT 1 FROM users WHERE id=?', (channel,)).fetchone():
                    raise Error(404, 'Channel not found')
                if body.get('enabled') is True:
                    c.execute('INSERT OR IGNORE INTO subscriptions VALUES(?,?)', (u['id'], channel))
                else:
                    c.execute('DELETE FROM subscriptions WHERE user_id=? AND channel_id=?', (u['id'], channel))
                c.commit()
                return self.send({'ok': True})
            match = re.fullmatch(r'/api/videos/(' + ID + r')/(like|comment|report|delete|edit|view)', path)
            if not match:
                raise Error(404, 'Not found')
            v = public(video(c, match[1]))
            action = match[2]
            if action in ('delete', 'edit'):
                if v['owner'] != u['id'] and not u['admin']:
                    raise Error(403, 'Only the owner or operator may change this video')
                if v['status'] in ('processing', 'uploading'):
                    raise Error(409, 'Wait for processing to finish')
                if action == 'delete':
                    c.execute('DELETE FROM videos WHERE id=?', (v['id'],))
                    shutil.rmtree(DATA / 'media' / v['id'], ignore_errors=True)
                else:
                    title, description = body.get('title'), body.get('description', '')
                    if not isinstance(title, str) or not title.strip() or len(title) > 200 or not isinstance(description, str) or len(description) > 5000:
                        raise Error(400, 'Title (1–200) and description (0–5000) required')
                    c.execute('UPDATE videos SET title=?,description=? WHERE id=?', (title.strip(), description, v['id']))
                c.commit()
                return self.send({'ok': True})
            if v['status'] != 'ready':
                raise Error(404, 'Not found')
            if action == 'like':
                if body.get('enabled') is True:
                    c.execute('INSERT OR IGNORE INTO likes VALUES(?,?)', (u['id'], v['id']))
                else:
                    c.execute('DELETE FROM likes WHERE user_id=? AND video_id=?', (u['id'], v['id']))
            elif action in ('comment', 'report'):
                self.limit(action, 20)
                value = body.get('text' if action == 'comment' else 'reason', '')
                if not isinstance(value, str) or not 1 <= len(value.strip()) <= 2000:
                    raise Error(400, 'Text must be 1–2000 characters')
                table, col = ('comments', 'text') if action == 'comment' else ('reports', 'reason')
                c.execute(f'INSERT INTO {table}(id,user_id,video_id,{col},created) VALUES(?,?,?,?,?)',
                          (uid(), u['id'], v['id'], value.strip(), int(time.time())))
            elif action == 'view':
                self.limit('view', 30)
                c.execute('UPDATE videos SET views=views+1 WHERE id=?', (v['id'],))
            c.commit()
            return self.send({'ok': True})

    def upload(self, u):
        title = unquote(self.headers.get('X-Video-Title', 'Untitled video'))
        description = unquote(self.headers.get('X-Video-Description', ''))
        if not title.strip() or len(title) > 200 or len(description) > 5000:
            raise Error(400, 'Title (1–200) and description (0–5000) required')
        length = self.length(MAX_UPLOAD)
        if length == 0:
            raise Error(400, 'Empty upload')
        self.limit('upload-bytes', 10)
        # Bound disk use and pending work per user before receiving the file.
        video_id = uid()
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            count = c.execute("SELECT count(*) FROM videos WHERE owner=? AND status IN ('processing','uploading')", (u['id'],)).fetchone()[0]
            if count >= 3:
                raise Error(429, 'Wait for your current uploads to finish')
            c.execute("INSERT INTO videos(id,owner,title,description,status,created) VALUES(?,?,?,?,'uploading',?)",
                      (video_id, u['id'], title.strip(), description, int(time.time())))
        source = DATA / 'incoming' / video_id
        try:
            with source.open('xb') as out:
                remaining = length
                while remaining:
                    block = self.rfile.read(min(remaining, 256 * 1024))
                    if not block:
                        raise Error(400, 'Incomplete upload')
                    out.write(block)
                    remaining -= len(block)
            with db() as c:
                c.execute("UPDATE videos SET status='processing' WHERE id=?", (video_id,))
        except BaseException:
            source.unlink(missing_ok=True)
            with db() as c:
                c.execute('DELETE FROM videos WHERE id=?', (video_id,))
            raise
        return self.send({'id': video_id, 'status': 'processing'}, 202)

    def file(self, path):
        if not path.is_file():
            raise Error(404, 'Not found')
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        byte_range = self.headers.get('Range')
        if byte_range:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', byte_range)
            if not match or not any(match.groups()):
                return self.send({'error': 'Invalid range'}, 416, {'Content-Range': f'bytes */{size}'})
            if match[1]:
                start = int(match[1])
                end = min(int(match[2]), size - 1) if match[2] else size - 1
            else:
                start = max(0, size - int(match[2]))
            if start > end or start >= size:
                return self.send({'error': 'Unsatisfiable range'}, 416, {'Content-Range': f'bytes */{size}'})
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(end - start + 1))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command == 'HEAD':
            return
        with path.open('rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                data = stream.read(min(remaining, 256 * 1024))
                if not data:
                    break
                self.wfile.write(data)
                remaining -= len(data)

    def log_message(self, fmt, *args):
        # Query strings can include search terms; don't retain them.
        print(self.command, urlsplit(self.path).path[:200], flush=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 32

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slots = threading.BoundedSemaphore(32)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def main():
    init()
    start_worker()
    port = int(os.environ.get('PORT', '3000'))
    server = Server((os.environ.get('BIND', '0.0.0.0'), port), Handler)
    print('MewTube listening at', ORIGIN, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
