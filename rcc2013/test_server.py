import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from PIL import Image
from server import camera_spec, Renderer, handler, ThreadingHTTPServer


class ControlPlaneTests(unittest.TestCase):
    def test_camera_rejects_executable_text_nonfinite_values_and_degenerate_view(self):
        for value in ({'position':['os.execute(1)',0,0]}, {'position':[float('nan'),0,0]},
                      {'position':[1,1,1],'target':[1,1,1]}, {'fov':True}, {'script':'anything'}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                camera_spec(value)

    def test_http_job_lifecycle_and_asset_path_boundary_with_a_mock_engine(self):
        calls=[]
        def mock_engine(studio,output,place,camera):
            output.mkdir(parents=True)
            Image.new('RGB',(2,2),(20,40,60)).save(output/'render.png')
            calls.append((place,camera))
            return {'engine_render_validated':True,'test_mock':True}
        with tempfile.TemporaryDirectory() as temporary:
            renderer=Renderer(Path(temporary)/'test.exe',Path(temporary)/'data',mock_engine)
            http=ThreadingHTTPServer(('127.0.0.1',0),handler(renderer))
            thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(http.server_port)
            try:
                bad=urllib.request.Request(base+'/v1/renders',json.dumps({'place_id':'../../secret'}).encode(),method='POST')
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(bad,timeout=3)
                self.assertEqual(error.exception.code,400)
                request=urllib.request.Request(base+'/v1/renders',b'{}',method='POST')
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
            finally:
                http.shutdown();http.server_close();renderer.close();thread.join(timeout=3)


if __name__=='__main__':
    unittest.main()
