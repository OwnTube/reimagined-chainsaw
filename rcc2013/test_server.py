import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from PIL import Image
from server import camera_spec, size_spec, Renderer, handler, ThreadingHTTPServer, AVATAR_CAMERA, HEADSHOT_CAMERA


class ControlPlaneTests(unittest.TestCase):
    def test_size_rejects_noninteger_oversized_and_incomplete_requests(self):
        for size in ({'width':True,'height':512},{'width':512.0,'height':512},
                     {'width':512},{'width':4096,'height':512},[],{}):
            with self.subTest(size=size),self.assertRaises(ValueError):size_spec(size)

    def test_camera_rejects_executable_text_nonfinite_values_and_degenerate_view(self):
        for value in ({'position':['os.execute(1)',0,0]}, {'position':[float('nan'),0,0]},
                      {'position':[1,1,1],'target':[1,1,1]}, {'fov':True}, {'script':'anything'}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                camera_spec(value)

    def test_http_job_lifecycle_and_asset_path_boundary_with_a_mock_engine(self):
        calls=[]
        def mock_engine(studio,output,place,camera,size,scene,render_type):
            output.mkdir(parents=True)
            image=Image.new('RGB' if render_type=='game_thumbnail' else 'RGBA',
                            (size['width'],size['height']) if size else (512,512),
                            (20,40,60) if render_type=='game_thumbnail' else (0,0,0,0))
            if render_type!='game_thumbnail':
                for y in range(20,80):
                    for x in range(20,80):image.putpixel((x,y),(20,40,60,255))
            image.save(output/'render.png')
            calls.append((place,camera,size,scene,render_type))
            return {'engine_render_validated':True,'test_mock':True,'subject_gui_validated':True,
                    'passes':[{'subject_gui_validated':True,'engine_render_validated':True}]*2}
        with tempfile.TemporaryDirectory() as temporary:
            renderer=Renderer(Path(temporary)/'test.exe',Path(temporary)/'data',mock_engine)
            http=ThreadingHTTPServer(('127.0.0.1',0),handler(renderer))
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(http.server_port)
            try:
                for route,mime in (('/','text/html'),('/logo.png','image/png'),('/app.js','text/javascript')):
                    with urllib.request.urlopen(base+route,timeout=3) as response:
                        self.assertEqual(response.headers.get_content_type(),mime)
                        self.assertTrue(response.read())
                bad=urllib.request.Request(base+'/v1/renders',json.dumps({'place_id':'../../secret'}).encode(),method='POST')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(bad,timeout=3)
                self.assertEqual(error.exception.code,400)
                request=urllib.request.Request(base+'/v1/renders',b'{"size":{"width":512,"height":512}}',method='POST')
                with urllib.request.urlopen(request,timeout=3) as response:
                    self.assertEqual(response.status,202);job=json.load(response)['id']
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    with urllib.request.urlopen(base+'/v1/renders/'+job,timeout=3) as response:
                        result=json.load(response)
                    if result['state']=='succeeded':break
                    time.sleep(0.02)
                self.assertEqual(result['state'],'succeeded')
                with urllib.request.urlopen(base+'/v1/renders/'+job+'/image',timeout=3) as response:
                    self.assertEqual(response.headers.get_content_type(),'image/png')
                    self.assertTrue(response.read().startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertEqual(len(calls),1)
                self.assertEqual(calls[0][2],{'width':512,'height':512})
                with urllib.request.urlopen(base+'/v1/renders',timeout=3) as response:
                    self.assertEqual(json.load(response)['jobs'][0]['id'],job)
                avatar=renderer.submit({'scene':'avatar'})
                headshot=renderer.submit({'type':'headshot'})
                renderer.close()
                self.assertEqual(calls[-2][1],AVATAR_CAMERA)
                self.assertEqual(calls[-2][-1],'full_body')
                self.assertEqual(calls[-1][1],HEADSHOT_CAMERA)
                self.assertEqual(calls[-1][-1],'headshot')
                self.assertEqual(renderer.get(avatar)['state'],'succeeded')
                self.assertEqual(renderer.get(headshot)['state'],'succeeded')
                for config in ({'scene':'other'},{'scene':'avatar','place_id':'a'*64},
                               {'type':'headshot','place_id':'a'*64},{'type':'game_thumbnail','scene':'avatar'},
                               {'type':'full_body','scene':'blocks'},{'type':'unknown'}):
                    with self.assertRaises(ValueError):renderer.submit(config)
            finally:
                http.shutdown();http.server_close();renderer.close();thread.join(timeout=3)


if __name__=='__main__':
    unittest.main()
