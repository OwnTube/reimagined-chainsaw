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
from urllib.parse import urlsplit, parse_qs
import uuid

from windows_probe import DEFAULT_CAMERA, AVATAR_CAMERA, HEADSHOT_CAMERA, render_scene
from assets import AssetStore
from item_framing import item_camera
from output_validation import validate_png

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
        self.assets=AssetStore(self.root/'assets')
        self.delivery_base=None
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
        if not isinstance(request,dict) or set(request)-{'place_id','asset_id','camera','size','scene','type'}:
            raise ValueError('Render request supports type, place_id, asset_id, camera, size, and scene only')
        request = dict(request)
        render_type=request.get('type','full_body' if request.get('scene')=='avatar' else 'game_thumbnail')
        if render_type not in ('headshot','full_body','game_thumbnail','item'):
            raise ValueError('type must be headshot, full_body, item, or game_thumbnail')
        player=render_type in ('headshot','full_body')
        scene = request.get('scene','item' if render_type=='item' else 'avatar' if player else 'blocks')
        if scene not in ('blocks','avatar','item'):raise ValueError('Unknown scene')
        if 'scene' in request and request.get('place_id') is not None:
            raise ValueError('Choose either a built-in scene or an uploaded place')
        if (player and (scene!='avatar' or request.get('place_id') is not None)) or (not player and scene=='avatar'):
            raise ValueError('Player thumbnail types require the avatar scene; game thumbnails require a place or blocks')
        asset=None
        if render_type=='item':
            identity=request.get('asset_id')
            if type(identity) is not int or not 1<=identity<=2147483647:raise ValueError('Item rendering requires an uploaded asset_id')
            asset=self.assets.info(identity)
            if not asset or asset['kind']!='model':raise ValueError('Item asset_id must identify an uploaded XML model')
            if scene!='item' or request.get('place_id') is not None:raise ValueError('Item rendering requires the item scene')
            if not self.delivery_base:raise ValueError('Local asset delivery is not running')
        elif request.get('asset_id') is not None or scene=='item':raise ValueError('asset_id is supported for item rendering only')
        request['type']=render_type
        request['scene'] = scene
        request['size'] = size_spec(request.get('size'))
        if (player or asset) and request['size'] is None:request['size']={'width':512,'height':512}
        defaults=item_camera(asset['metadata']['bounds'],request['size']) if asset else HEADSHOT_CAMERA if render_type=='headshot' else AVATAR_CAMERA if player else DEFAULT_CAMERA
        request['camera'] = camera_spec(request.get('camera',{}),defaults)
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
            output=self.root/'jobs'/job
            if request['type']=='item':
                asset=self.assets.info(request['asset_id']);sequence=self.assets.sequence
                item={'url':self.delivery_base+'/assets/'+str(asset['id'])+'/content','parts':asset['metadata']['parts']}
                report=render_scene(self.studio,output,None,request['camera'],request['size'],'item','item',item)
                trace=self.assets.trace(sequence)
                expected={asset['id'],*asset['metadata']['dependencies']}
                delivered={x['id'] for x in trace}
                report.update({'asset_id':asset['id'],'asset_sha256':asset['sha256'],
                               'asset_sanitizer':asset['metadata'],'asset_delivery_requests':trace,
                               'asset_delivery_validated':expected.issubset(delivered)})
                if not report['asset_delivery_validated']:raise ValueError('Engine did not fetch the item and every local dependency')
            else:report = self.engine(self.studio,output,place,request['camera'],request['size'],request['scene'],request['type'])
            report.setdefault('type',request['type'])
            if report.get('engine_render_validated'):
                report['png_sha256']=validate_png(output/'render.png',request['type'],request['size'],report)
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

    def image(self, job):
        path=self.root/'jobs'/job['id']/'render.png'
        try:data=path.read_bytes()
        except OSError:raise ValueError('Verified image is unavailable')
        if hashlib.sha256(data).hexdigest()!=job['result'].get('png_sha256'):
            raise ValueError('Image no longer matches the verified render')
        dimensions=job['result'].get('image_size')
        size={'width':dimensions[0],'height':dimensions[1]} if dimensions else None
        validate_png(path,job['result'].get('type'),size,job['result'])
        return data

    def recent(self):
        with self.connect() as db:
            rows = db.execute('SELECT id,state,result FROM jobs ORDER BY rowid DESC LIMIT 20').fetchall()
        return [{'id':r[0],'state':r[1],'result':json.loads(r[2])} for r in rows]


def handler(renderer):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            host,port=self.server.server_address
            if host!='127.0.0.1':raise ValueError('Asset delivery requires a numeric loopback listener')
            renderer.delivery_base='http://127.0.0.1:'+str(port)
        def log_message(self, *_):
            pass

        def send(self, status, data, content_type='application/json', headers=None):
            if not isinstance(data,bytes):
                data=json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','public, max-age=31536000, immutable' if headers else 'no-store')
            for name,value in (headers or {}).items():self.send_header(name,value)
            self.end_headers()
            if self.command!='HEAD':self.wfile.write(data)

        def do_GET(self):
            path=urlsplit(self.path).path
            asset=re.fullmatch(r'/assets/([1-9][0-9]{0,9})/content',path)
            legacy=path.lower().rstrip('/') in ('/asset','/v1/asset')
            if asset or legacy:
                identity=asset[1] if asset else parse_qs(urlsplit(self.path).query).get('id',[''])[0]
                if not re.fullmatch('[1-9][0-9]{0,9}',identity) or int(identity)>2147483647:return self.send(400,{'error':'Invalid asset id'})
                try:data,info,digest=renderer.assets.content(int(identity),renderer.delivery_base)
                except KeyError:return self.send(404,{'error':'Unknown local asset'})
                except (ValueError,OSError) as error:return self.send(409,{'error':str(error)})
                headers={'ETag':'"'+digest+'"','X-Asset-SHA256':digest,'X-Asset-Source-SHA256':info['sha256']}
                if self.headers.get('If-None-Match')==headers['ETag']:return self.send(304,b'',info['mime'],headers)
                return self.send(200,data,info['mime'],headers)
            metadata=re.fullmatch(r'/v1/assets/([1-9][0-9]{0,9})',path)
            if metadata:
                if int(metadata[1])>2147483647:return self.send(400,{'error':'Invalid asset id'})
                info=renderer.assets.info(int(metadata[1]))
                return self.send(200,info) if info else self.send(404,{'error':'Unknown local asset'})
            assets = {'/':('index.html','text/html; charset=utf-8'),
                      '/app.js':('app.js','text/javascript; charset=utf-8'),
                      '/style.css':('style.css','text/css; charset=utf-8'),
                      '/thumbnails.css':('thumbnails.css','text/css; charset=utf-8'),
                      '/logo.png':('logo.png','image/png')}
            if path in assets:
                name,content_type = assets[path]
                return self.send(200,(STATIC/name).read_bytes(),content_type)
            if path=='/health':
                return self.send(200,{'service':'RCC2013','engine':'Studio 2013.11.25.2',
                    'render_method':'native viewport capture','studio_present':renderer.studio.is_file()})
            if path=='/v1/presets':return self.send(200,{'full_body':AVATAR_CAMERA,'headshot':HEADSHOT_CAMERA,'game_thumbnail':DEFAULT_CAMERA})
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
                try:return self.send(200,renderer.image(job),'image/png')
                except ValueError as error:return self.send(409,{'error':str(error)})
            return self.send(200,job)

        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length','-1'))
                path=urlsplit(self.path).path
                limit=8*1024*1024 if path in ('/v1/places','/v1/assets') else 65536
                if length<0 or length>limit:
                    return self.send(413,{'error':'Missing or excessive Content-Length'})
                content=self.rfile.read(length)
                if len(content)!=length:raise ValueError('Incomplete request body')
                if path=='/v1/assets':
                    kind=parse_qs(urlsplit(self.path).query).get('kind',['model'])[0]
                    return self.send(201,renderer.assets.upload(kind,content))
                if path=='/v1/places':
                    return self.send(201,{'place_id':renderer.upload(content)})
                if path=='/v1/renders':
                    return self.send(202,{'id':renderer.submit(json.loads(content))})
                return self.send(404,{'error':'Not found'})
            except (ValueError,UnicodeError) as error:
                return self.send(400,{'error':str(error)})
        do_HEAD=do_GET
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
