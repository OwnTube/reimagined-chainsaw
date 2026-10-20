import hashlib
import json
from pathlib import Path
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from PIL import Image
from assets import AssetStore
from item_fixture import mesh,texture,model
from item_framing import item_camera,dot,unit
from output_validation import validate_png
from server import Renderer,handler,ThreadingHTTPServer


class AssetTests(unittest.TestCase):
    def test_model_dependencies_and_active_content_are_sanitized_before_delivery(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=AssetStore(temporary)
            png=store.upload('texture',texture());geometry=store.upload('mesh',mesh())
            asset=store.upload('model',model(geometry['id'],png['id']))
            self.assertEqual(asset['metadata']['stripped_instances'],{'BillboardGui':1,'Script':1,'Humanoid':1})
            self.assertEqual(asset['metadata']['parts'],4)
            data,_,digest=store.content(asset['id'],'http://127.0.0.1:8123')
            self.assertNotIn(b'SHOULD_NOT',data);self.assertNotIn(b'BillboardGui',data);self.assertNotIn(b'Humanoid',data)
            for identity in (png['id'],geometry['id']):self.assertIn(('http://127.0.0.1:8123/assets/'+str(identity)+'/content').encode(),data)
            self.assertEqual(digest,hashlib.sha256(data).hexdigest())
            self.assertEqual(store.upload('texture',texture())['id'],png['id'])
            (Path(temporary)/png['sha256']).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):store.content(png['id'],'http://127.0.0.1:8123')

    def test_rejects_external_references_invalid_meshes_and_nonstatic_models(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=AssetStore(temporary)
            for data in (b'<!DOCTYPE roblox><roblox/>',b'<roblox><Item class="RemoteEvent"/></roblox>',
                         model(999,999).replace(b'rbxassetid://999',b'http://example.org/private'),
                         b'<roblox><Item class="Model"/></roblox>'):
                with self.assertRaises(ValueError):store.upload('model',data)
            broken=bytearray(mesh());struct.pack_into('<I',broken,len(broken)-12,999999)
            with self.assertRaises(ValueError):store.upload('mesh',bytes(broken))
            with self.assertRaises(ValueError):store.upload('texture',b'not a png')

    def test_real_http_delivery_bytes_mime_cache_validation_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            renderer=Renderer(Path(temporary)/'test.exe',Path(temporary)/'data')
            server=ThreadingHTTPServer(('127.0.0.1',0),handler(renderer))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                content=texture()
                with urllib.request.urlopen(urllib.request.Request(base+'/v1/assets?kind=texture',content,method='POST')) as response:asset=json.load(response)
                for path in ('/assets/'+str(asset['id'])+'/content','/asset/?id='+str(asset['id']),'/Asset?id='+str(asset['id']),'/v1/asset?id='+str(asset['id'])):
                    with urllib.request.urlopen(base+path) as response:
                        self.assertEqual(response.headers.get_content_type(),'image/png')
                        self.assertEqual(response.read(),content);etag=response.headers['ETag']
                with urllib.request.urlopen(base+'/v1/assets/'+str(asset['id'])) as response:self.assertEqual(json.load(response)['sha256'],hashlib.sha256(content).hexdigest())
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(base+'/asset/?id='+str(asset['id']),headers={'If-None-Match':etag}))
                self.assertEqual(error.exception.code,304)
                for path in ('/asset/?id=../../private','/assets/999/content'):
                    with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+path)
            finally:server.shutdown();server.server_close();renderer.close();thread.join(timeout=3)

    def test_fit_keeps_all_bounds_corners_inside_square_portrait_and_wide_frames(self):
        import math
        bounds={'min':[-2,-1,-3],'max':[4,8,2]}
        for width,height in ((512,512),(450,600),(800,450)):
            camera=item_camera(bounds,{'width':width,'height':height})
            backward=unit([p-t for p,t in zip(camera['position'],camera['target'])])
            right=unit([-backward[2],0,backward[0]])
            up=[backward[1]*right[2]-backward[2]*right[1],backward[2]*right[0]-backward[0]*right[2],backward[0]*right[1]-backward[1]*right[0]]
            for bits in range(8):
                delta=[bounds['max' if bits&(1<<i) else 'min'][i]-camera['position'][i] for i in range(3)]
                depth=-dot(delta,backward)
                self.assertGreater(depth,0)
                self.assertLess(abs(dot(delta,up))/depth,math.tan(math.radians(camera['fov']/2)))
                self.assertLess(abs(dot(delta,right))/depth,math.tan(math.radians(camera['fov']/2))*width/height)

    def test_output_rejects_opaque_background_missing_gui_evidence_and_clipped_items(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'render.png';image=Image.new('RGBA',(64,64),(0,0,0,0))
            for y in range(20,44):
                for x in range(20,44):image.putpixel((x,y),(0,0,0,255))
            image.save(path)
            report={'subject_gui_validated':True,'passes':[{'subject_gui_validated':True,'engine_render_validated':True}]*2}
            self.assertEqual(validate_png(path,'item',{'width':64,'height':64},report),hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):validate_png(path,'item',None,{})
            image.putpixel((0,25),(255,255,255,255));image.save(path)
            with self.assertRaises(ValueError):validate_png(path,'item',None,report)
            Image.new('RGBA',(64,64),(255,255,255,255)).save(path)
            with self.assertRaises(ValueError):validate_png(path,'item',None,report)


if __name__=='__main__':unittest.main()
