"""Exercise the HTTP service with real FFmpeg uploads, SQLite, and sessions."""
import http.cookiejar
import gzip
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = Path(cls.tmp.name)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            cls.port = s.getsockname()[1]
        cls.origin = f'http://localhost:{cls.port}'
        cls.log = (cls.data / 'server.log').open('w')
        cls.process = subprocess.Popen([sys.executable, '-m', 'mewtube.server'], cwd=ROOT,
            env={**os.environ, 'DATA_DIR': str(cls.data), 'PORT': str(cls.port),
                 'BIND': '127.0.0.1', 'PUBLIC_ORIGIN': cls.origin}, stdout=cls.log, stderr=cls.log)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.origin + '/healthz', timeout=1).close()
                break
            except OSError:
                time.sleep(.05)
        else:
            cls.process.terminate()
            raise RuntimeError('Service did not start')
        cls.fixture = cls.data / 'sample.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
            'testsrc2=size=320x180:rate=15', '-f', 'lavfi', '-i', 'sine=frequency=440',
            '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(cls.fixture)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.log.close()
        cls.tmp.cleanup()

    def setUp(self):
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, body=None, client=None, headers=None, raw=None, method=None):
        hdr = {'Origin': self.origin, 'X-MewTube': '1'}
        hdr.update(headers or {})
        payload = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if body is not None:
            hdr['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.origin + path, data=payload, headers=hdr, method=method)
        try:
            response = (client or self.client).open(req, timeout=20)
        except urllib.error.HTTPError as e:
            response = e
        data = response.read()
        if response.headers.get('Content-Type', '').startswith('application/json'):
            data = json.loads(data)
        return response.status, data, response.headers

    def account(self, name):
        status, data, headers = self.request('/api/register', {'username': name, 'password': 'long-test-password'})
        self.assertEqual(status, 200, data)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        return data['user']

    def upload(self, title='A real video'):
        status, data, _ = self.request('/api/upload', raw=self.fixture.read_bytes(),
            headers={'X-Video-Title': urllib.parse.quote(title), 'X-Video-Description': 'Local%20description'})
        self.assertEqual(status, 202, data)
        vid = data['id']
        for _ in range(100):
            status, data, _ = self.request('/api/videos/' + vid)
            if data['video']['status'] != 'processing':
                break
            time.sleep(.1)
        self.assertEqual(data['video']['status'], 'ready', data)
        return data['video']

    def test_01_guest_and_csrf(self):
        self.assertEqual(self.request('/api/me')[1], {'user': None})
        self.assertEqual(self.request('/auth-return.js')[0], 200)
        self.assertEqual(self.request('/api/studio')[0], 401)
        self.assertEqual(self.request('/api/videos?feed=subscriptions')[0], 401)
        self.assertEqual(self.request('/youtubei/v1/player', {'videoId':123})[0], 400)
        self.assertEqual(self.request('/youtubei/v1/log_event', raw=b'\x00\xffbinary')[0], 200)
        self.assertEqual(self.request('/api/register', {}, headers={'Origin':'https://evil.test'})[0], 403)
        self.assertEqual(self.request('/api/register', {}, headers={'X-MewTube':''})[0], 403)
        self.assertEqual(self.request('/api/register', {'username':'x', 'password':'short'})[0], 400)
        self.assertEqual(self.request('/media/../../server.py')[0], 404)
        self.assertEqual(self.request('/client-assets/../../server.py')[0], 404)
        self.assertEqual(self.request('/official')[0], 503)

    def test_02_auth_lifecycle(self):
        self.account('alice')
        self.assertEqual(self.request('/api/register', {'username':'ALICE','password':'long-test-password'})[0], 409)
        self.assertEqual(self.request('/api/me')[1]['user']['username'], 'alice')
        self.assertEqual(self.request('/api/logout', {})[0], 200)
        self.assertIsNone(self.request('/api/me')[1]['user'])
        self.assertEqual(self.request('/api/login', {'username':'alice','password':'incorrect-password'})[0], 401)
        self.assertEqual(self.request('/api/login', {'username':'alice','password':'long-test-password'})[0], 200)

    def test_03_real_media_and_compatibility(self):
        self.account('creator')
        v = self.upload('Cats & <robots> 🐈')
        self.assertEqual(v['title'], 'Cats & <robots> 🐈')
        self.assertEqual(v['description'], 'Local description')
        path = f"/media/{v['id']}/video.mp4"
        status, full, headers = self.request(path)
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'video/mp4')
        self.assertIn(b'ftyp', full[:32])
        status, chunk, hdr = self.request(path, headers={'Range':'bytes=0-31'})
        self.assertEqual(status, 206)
        self.assertEqual(chunk, full[:32])
        self.assertEqual(hdr['Content-Range'], f'bytes 0-31/{len(full)}')
        self.assertEqual(self.request(path, headers={'Range':'bytes=-16'})[1], full[-16:])
        self.assertEqual(self.request(path, headers={'Range':'bytes=999999999-'})[0], 416)
        self.assertEqual(self.request(path, method='HEAD')[1], b'')
        self.assertTrue(self.request(f"/media/{v['id']}/thumb.jpg")[1].startswith(b'\xff\xd8'))
        self.assertEqual(len(self.request('/api/videos?q=Cats')[1]['videos']), 1)
        response = self.request('/youtubei/v1/player', {'videoId':v['id']})[1]
        self.assertEqual(response['playabilityStatus']['status'], 'OK')
        self.assertTrue(response['responseContext']['mainAppWebResponseContext']['mewtubeLocalResponse'])
        self.assertEqual(response['streamingData']['formats'][0]['url'], self.origin + path)
        self.assertEqual(response['videoDetails']['thumbnail']['thumbnails'][0]['url'],
                         self.origin + f"/media/{v['id']}/thumb.jpg")
        missing = self.request('/youtubei/v1/player', {'videoId':'___________'})[1]
        self.assertEqual(missing['playabilityStatus']['status'], 'ERROR')
        self.assertNotIn('mewtubeLocalResponse', missing['responseContext']['mainAppWebResponseContext'])
        search = self.request('/youtubei/v1/search', {'query':'Cats'})[1]
        items = search['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents']
        self.assertEqual(items[0]['videoRenderer']['title']['runs'][0]['text'], v['title'])
        self.assertEqual(self.request('/youtubei/v1/browse', {})[0], 200)
        self.assertEqual(self.request('/youtubei/v1/next', {'videoId':v['id']})[0], 200)
        self.assertEqual(self.request('/youtubei/v1/not_supported', {})[0], 501)
        self.assertEqual(self.request('/api/videos/' + v['id'] + '/delete', {})[0], 200)
        self.assertEqual(self.request(path)[0], 404)

    def test_08_captured_like_uses_local_session_and_persists(self):
        self.account('native_liker')
        v = self.upload('Native mutation fixture')
        body = {'target': {'videoId': v['id']}}
        compressed = gzip.compress(json.dumps(body).encode())
        encoding_headers = {'Content-Type':'application/json', 'Content-Encoding':'gzip'}
        self.assertEqual(self.request('/youtubei/v1/like/like', raw=compressed, headers=encoding_headers)[0], 200)
        self.assertEqual(self.request('/youtubei/v1/like/removelike', raw=compressed, headers=encoding_headers)[0], 200)
        self.assertEqual(self.request('/youtubei/v1/like/like', raw=b'not gzip', headers=encoding_headers)[0], 400)
        self.assertEqual(self.request('/youtubei/v1/like/like', raw=compressed[:-4], headers=encoding_headers)[0], 400)
        oversized = gzip.compress(b' ' * (1024 * 1024 + 1))
        self.assertEqual(self.request('/youtubei/v1/like/like', raw=oversized, headers=encoding_headers)[0], 413)
        self.assertEqual(self.request('/youtubei/v1/like/like', body, headers={'Content-Encoding':'br'})[0], 415)
        guest = urllib.request.build_opener()
        self.assertEqual(self.request('/youtubei/v1/like/like', body, client=guest)[0], 401)
        self.assertEqual(self.request('/youtubei/v1/like/like', body,
            headers={'Origin':'https://evil.test'})[0], 403)
        for invalid in ({}, {'target': []}, {'target': {'videoId': 123}}, {'target': {'videoId':'../secret'}}):
            self.assertEqual(self.request('/youtubei/v1/like/like', invalid)[0], 400)
        self.assertEqual(self.request('/youtubei/v1/like/like', {'target': {'videoId':'___________'}})[0], 404)
        def native_button(client=None):
            result = self.request('/youtubei/v1/next', {'videoId':v['id']}, client=client)[1]
            primary = result['contents']['twoColumnWatchNextResults']['results']['results']['contents'][0]['videoPrimaryInfoRenderer']
            return primary['videoActions']['menuRenderer']['topLevelButtons'][0]['toggleButtonRenderer']
        self.assertFalse(native_button()['isToggled'])
        guest_button = native_button(guest)
        guest_url = guest_button['defaultNavigationEndpoint']['urlEndpoint']['url']
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(guest_url).query)['return_to'],
                         ['/official?v=' + v['id']])
        for _ in range(2):
            self.assertEqual(self.request('/youtubei/v1/like/like', body)[0], 200)
        self.assertEqual(self.request('/api/videos/'+v['id'])[1]['video']['likes'], 1)
        self.assertTrue(native_button()['isToggled'])
        self.assertEqual(native_button()['defaultText']['simpleText'], '0')
        self.assertEqual(native_button()['toggledText']['simpleText'], '1')
        for _ in range(2):
            self.assertEqual(self.request('/youtubei/v1/like/removelike', body)[0], 200)
        self.assertFalse(self.request('/api/videos/'+v['id'])[1]['video']['liked'])
        self.assertFalse(native_button()['isToggled'])
        first_client = self.client
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.account('other_native_liker')
        self.assertEqual(self.request('/youtubei/v1/like/like', body)[0], 200)
        self.assertTrue(native_button()['isToggled'])
        self.assertFalse(native_button(first_client)['isToggled'], 'Like state must be scoped to the local session')

    def test_04_interactions_ownership_and_moderation(self):
        owner = self.account('owner')
        v = self.upload()
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        viewer = self.account('viewer')
        prefix = '/api/videos/' + v['id']
        self.assertEqual(self.request(prefix + '/delete', {})[0], 403)
        self.assertEqual(self.request(prefix + '/edit', {'title':'Hijack'})[0], 403)
        for _ in range(2):
            self.assertEqual(self.request(prefix + '/like', {'enabled':True})[0], 200)
        self.assertEqual(self.request(prefix)[1]['video']['likes'], 1)
        self.assertEqual(self.request(prefix)[1]['video']['liked'], True)
        self.assertEqual(self.request(prefix + '/comment', {'text':'<script>alert(1)</script>'})[0], 200)
        self.assertEqual(self.request(prefix)[1]['comments'][0]['text'], '<script>alert(1)</script>')
        self.assertEqual(self.request('/api/subscribe', {'channelId':owner['id'],'enabled':True})[0], 200)
        self.assertTrue(any(x['id'] == v['id'] for x in self.request('/api/videos?feed=subscriptions')[1]['videos']))
        self.assertEqual(self.request(prefix + '/report', {'reason':'Test moderation'})[0], 200)
        self.assertEqual(self.request('/api/admin')[0], 403)
        self.request('/youtubei/v1/unknown_moderation_test', {})
        with sqlite3.connect(self.data / 'mewtube.sqlite3') as c:
            c.execute('UPDATE users SET admin=1 WHERE id=?', (viewer['id'],))
        self.assertEqual(len(self.request('/api/admin')[1]['reports']), 1)
        self.assertTrue(self.request('/api/admin')[1]['unknown'])
        self.assertEqual(self.request(prefix + '/delete', {})[0], 200)

    def test_05_reject_nonvideo_and_playlists(self):
        self.account('invalid_upload')
        for raw in (b'not a video', b'#EXTM3U\n#EXTINF:1\nfile:///etc/passwd\n'):
            status, data, _ = self.request('/api/upload', raw=raw)
            self.assertEqual(status, 202)
            for _ in range(50):
                v = self.request('/api/videos/' + data['id'])[1]['video']
                if v['status'] == 'failed':
                    break
                time.sleep(.1)
            self.assertEqual(v['status'], 'failed')
            self.assertNotIn('/etc/', v['error'])
            self.assertEqual(self.request(f"/media/{v['id']}/video.mp4")[0], 404)

    def test_06_restart_preserves_sessions_and_recovers_jobs(self):
        owner = self.account('durable')
        v = self.upload('Survives a restart')
        partial_id, queued_id = 'partial0001', 'queued00001'
        (self.data / 'incoming' / partial_id).write_bytes(b'partial body')
        with sqlite3.connect(self.data / 'mewtube.sqlite3') as c:
            c.execute('INSERT INTO videos(id,owner,title,status,created) VALUES(?,?,?,?,?)',
                      (partial_id, owner['id'], 'Partial fixture', 'uploading', int(time.time())))
        self.assertEqual(self.request('/api/videos/' + partial_id + '/delete', {})[0], 409)
        self.process.terminate()
        self.process.wait(timeout=10)
        # Queue this job while the service is down, so only the restarted worker can handle it.
        (self.data / 'incoming' / queued_id).write_bytes(self.fixture.read_bytes())
        with sqlite3.connect(self.data / 'mewtube.sqlite3') as c:
            c.execute('INSERT INTO videos(id,owner,title,status,created) VALUES(?,?,?,?,?)',
                      (queued_id, owner['id'], 'Recovery fixture', 'processing', int(time.time())))
        type(self).process = subprocess.Popen([sys.executable, '-m', 'mewtube.server'], cwd=ROOT,
            env={**os.environ, 'DATA_DIR':str(self.data), 'PORT':str(self.port),
                 'BIND':'127.0.0.1', 'PUBLIC_ORIGIN':self.origin}, stdout=self.log, stderr=self.log)
        for _ in range(100):
            try:
                if self.request('/healthz')[0] == 200:
                    break
            except OSError:
                pass
            time.sleep(.05)
        self.assertEqual(self.request('/api/me')[1]['user']['username'], 'durable')
        self.assertEqual(self.request('/api/videos/' + v['id'])[1]['video']['status'], 'ready')
        self.assertEqual(self.request('/api/videos/' + partial_id)[1]['video']['status'], 'failed')
        self.assertFalse((self.data / 'incoming' / partial_id).exists())
        for _ in range(100):
            queued = self.request('/api/videos/' + queued_id)[1]['video']
            if queued['status'] != 'processing':
                break
            time.sleep(.1)
        self.assertEqual(queued['status'], 'ready', queued)

    def test_07_official_navigation_uses_watch_shell_until_explicit_exit(self):
        video_id, owner_id = 'public00001', 'fixture0001'
        with sqlite3.connect(self.data / 'mewtube.sqlite3') as c:
            c.execute('INSERT INTO users(id,username,password) VALUES(?,?,?)', (owner_id, 'route_fixture', 'unused'))
            c.execute("INSERT INTO videos(id,owner,title,status,duration,created) VALUES(?,?,?,'ready',1,?)",
                      (video_id, owner_id, 'Pinned watch entry', int(time.time())))
        client = self.data / 'client'
        client.mkdir(exist_ok=True)
        markup = '<html><head></head><script>var ytInitialData={};var ytInitialPlayerResponse={};var original="jNQXAC9IVRw";</script><ytd-app></ytd-app></html>'
        (client / 'index.html').write_text(markup)
        (client / 'watch.html').write_text(markup)
        (client / 'manifest.json').write_text('{"assets":[],"watchSourceId":"jNQXAC9IVRw"}')
        status, home, _ = self.request('/official')
        self.assertEqual(status, 200)
        self.assertIn(b'/bridge.js', home)
        status, watch, _ = self.request('/watch?v=' + video_id)
        self.assertEqual(status, 200)
        self.assertIn(b'Pinned watch entry', watch)
        self.assertIn(b'"playabilityStatus":{"status":"OK"}', watch)
        self.assertNotIn(b'jNQXAC9IVRw', watch)
        self.assertNotIn(b'/app.js', watch)
        self.assertIn(b'/app.js', self.request('/?native=1')[1])
        self.assertIn(b'/app.js', self.request('/watch?v=' + video_id)[1])


if __name__ == '__main__':
    unittest.main()
