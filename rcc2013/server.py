"""Local render-job API backed by the pinned 2013 Studio engine."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import sqlite3
import threading
import time
from urllib.parse import urlsplit
import uuid

from windows_probe import DEFAULT_CAMERA, AVATAR_CAMERA, render_scene

STATIC = Path(__file__).with_name('static')


def size_spec(value):
    if value is None:
        return None
    if (not isinstance(value,dict) or set(value)!={'width','height'} or
        any(type(v) is not int or not 128<=v<=2048 for v in value.values())):
        raise ValueError('size requires integer width and height between 128 and 2048')
    return dict(value)


def camera_spec(value, defaults=None):
    if not isinstance(value, dict) or set(value)-set(DEFAULT_CAMERA):
        raise ValueError('camera supports position, target, and fov only')
    result = {**(defaults or DEFAULT_CAMERA), **value}
    for key in ('position','target'):
        vector = result[key]
        if not isinstance(vector,list) or len(vector)!=3 or any(
            type(v) not in (int,float) or not math.isfinite(v) or abs(v)>4096 for v in vector):
            raise ValueError('Invalid camera '+key)
    if sum((a-b)**2 for a,b in zip(result['position'],result['target']))<0.0001:
        raise ValueError('Camera position and target must differ')
    if type(result['fov']) not in (int,float) or not math.isfinite(result['fov']) or not 10<=result['fov']<=100:
        raise ValueError('Camera fov must be between 10 and 100')
    return result


class Renderer:
    def __init__(self, studio, root, engine=render_scene):
        self.studio, self.root, self.engine = Path(studio), Path(root).resolve(), engine
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/'places').mkdir(exist_ok=True)
        (self.root/'jobs').mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.worker = ThreadPoolExecutor(max_workers=1)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, state TEXT, request TEXT, result TEXT)')
            db.execute("UPDATE jobs SET state='failed',result=? WHERE state IN ('queued','running')",
                       (json.dumps({'error':'Worker restarted before job completion'}),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root/'jobs.sqlite3',timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def upload(self, content):
        if not content.startswith((b'<roblox',b'<?xml')):
            raise ValueError('Expected a Roblox XML or binary place')
        identity = hashlib.sha256(content).hexdigest()
        path = self.root/'places'/(identity+'.rbxl')
        if not path.exists():
            path.write_bytes(content)
        return identity

    def submit(self, request):
        if not isinstance(request,dict) or set(request)-{'place_id','camera','size','scene'}:
            raise ValueError('Render request supports place_id, camera, size, and scene only')
        request = dict(request)
        scene = request.get('scene','blocks')
        if scene not in ('blocks','avatar'):
            raise ValueError('scene must be blocks or avatar')
        if 'scene' in request and request.get('place_id') is not None:
            raise ValueError('Choose either a built-in scene or an uploaded place')
        request['scene'] = scene
        request['camera'] = camera_spec(request.get('camera',{}),AVATAR_CAMERA if scene=='avatar' else DEFAULT_CAMERA)
        request['size'] = size_spec(request.get('size'))
        identity = request.get('place_id')
        if identity is not None and (not isinstance(identity,str) or not re.fullmatch('[a-f0-9]{64}',identity)
                                    or not (self.root/'places'/(identity+'.rbxl')).is_file()):
            raise ValueError('Unknown place_id; upload the place first')
        with self.lock, self.connect() as db:
            if db.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0]>=16:
                raise ValueError('Render queue is full')
            job = uuid.uuid4().hex
            db.execute('INSERT INTO jobs VALUES (?,?,?,?)',(job,'queued',json.dumps(request),'{}'))
        self.worker.submit(self.execute,job,request)
        return job

    def execute(self, job, request):
        with self.connect() as db:
            db.execute("UPDATE jobs SET state='running' WHERE id=?",(job,))
        try:
            place = self.root/'places'/(request['place_id']+'.rbxl') if request.get('place_id') else None
            report = self.engine(self.studio,self.root/'jobs'/job,place,request['camera'],request['size'],request['scene'])
            state = 'succeeded' if report.get('engine_render_validated') else 'failed'
        except Exception as error:
            report,state = {'error':str(error),'engine_render_validated':False},'failed'
        with self.connect() as db:
            db.execute('UPDATE jobs SET state=?,result=? WHERE id=?',(state,json.dumps(report),job))

    def get(self, job):
        if not re.fullmatch('[a-f0-9]{32}',job):
            return None
        with self.connect() as db:
            row = db.execute('SELECT state,result FROM jobs WHERE id=?',(job,)).fetchone()
        return {'id':job,'state':row[0],'result':json.loads(row[1])} if row else None

    def close(self):
        self.worker.shutdown(wait=True)

    def recent(self):
        with self.connect() as db:
            rows = db.execute('SELECT id,state,result FROM jobs ORDER BY rowid DESC LIMIT 20').fetchall()
        return [{'id':r[0],'state':r[1],'result':json.loads(r[2])} for r in rows]


def handler(renderer):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, data, content_type='application/json'):
            if not isinstance(data,bytes):
                data=json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path=urlsplit(self.path).path
            assets = {'/':('index.html','text/html; charset=utf-8'),
                      '/app.js':('app.js','text/javascript; charset=utf-8'),
                      '/style.css':('style.css','text/css; charset=utf-8'),
                      '/logo.png':('logo.png','image/png')}
            if path in assets:
                name,content_type = assets[path]
                return self.send(200,(STATIC/name).read_bytes(),content_type)
            if path=='/health':
                return self.send(200,{'service':'RCC2013','engine':'Studio 2013.11.25.2',
                    'render_method':'native viewport capture','studio_present':renderer.studio.is_file()})
            if path=='/v1/renders':
                return self.send(200,{'jobs':renderer.recent()})
            match=re.fullmatch('/v1/renders/([a-f0-9]{32})(/image)?',path)
            if not match:
                return self.send(404,{'error':'Not found'})
            job=renderer.get(match[1])
            if job is None:
                return self.send(404,{'error':'Unknown job'})
            if match[2]:
                if job['state']!='succeeded':
                    return self.send(409,{'error':'Render is not ready','state':job['state']})
                return self.send(200,(renderer.root/'jobs'/job['id']/'render.png').read_bytes(),'image/png')
            return self.send(200,job)

        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','-1'))
                path=urlsplit(self.path).path
                limit=8*1024*1024 if path=='/v1/places' else 65536
                if length<0 or length>limit:
                    return self.send(413,{'error':'Missing or excessive Content-Length'})
                content=self.rfile.read(length)
                if path=='/v1/places':
                    return self.send(201,{'place_id':renderer.upload(content)})
                if path=='/v1/renders':
                    return self.send(202,{'id':renderer.submit(json.loads(content))})
                return self.send(404,{'error':'Not found'})
            except (ValueError,UnicodeError) as error:
                return self.send(400,{'error':str(error)})
    return Handler


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio',type=Path,default=Path('vendor/studio/RobloxStudioBeta.exe'))
    parser.add_argument('--data',type=Path,default=Path('data'))
    parser.add_argument('--port',type=int,default=64313)
    args=parser.parse_args()
    renderer=Renderer(args.studio,args.data)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(renderer))
    print('RCC2013 ready at http://127.0.0.1:'+str(server.server_port),flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        renderer.close()
