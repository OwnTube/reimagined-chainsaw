"""Exercise actual rasterization and the queue with subprocesses forbidden."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
from assets import AssetStore
from item_fixture import mesh,model,texture
from item_framing import item_camera
from software_render import cube,transform,rasterize,render,xml_scene,validate
from server import Renderer

class SoftwareTests(unittest.TestCase):
    def test_black_white_blue_are_preserved_without_background_keying(self):
        geometry=[transform(cube((1,2,1),color),(x,0,0)) for x,color in [(-1.5,(0,0,0)),(0,(255,255,255)),(1.5,(0,0,255))]]
        with patch('subprocess.Popen',side_effect=AssertionError('Process launch forbidden')):
            image,stats=rasterize(geometry,{'position':[0,0,-8],'target':[0,0,0],'fov':45},{'width':256,'height':256})
        rgba=np.array(image);pixels=rgba[rgba[:,:,3]==255,:3]
        self.assertGreater(stats['depth_fragments'],100)
        self.assertGreater(np.count_nonzero(rgba[:,:,3]==0),100)
        self.assertTrue((pixels.max(axis=1)==0).any())
        self.assertTrue((pixels.min(axis=1)>180).any())
        self.assertTrue(((pixels[:,2]>100)&(pixels[:,0]<10)).any())

    def test_real_item_mesh_texture_gui_cleanup_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as d,patch('subprocess.Popen',side_effect=AssertionError('No Studio permitted')):
            root=Path(d);assets=AssetStore(root/'assets')
            m=assets.upload('mesh',mesh());t=assets.upload('texture',texture());item=assets.upload('model',model(m['id'],t['id']))
            size={'width':256,'height':256};camera=item_camera(item['metadata']['bounds'],size)
            r=render(root,root/'job',None,camera,size,'item','item',assets,item['id'])
            self.assertTrue(r['custom_render_validated']);self.assertFalse(r['engine_render_validated']);self.assertFalse(r['studio_launched'])
            self.assertEqual(len(r['assets']),2)
            self.assertEqual(item['metadata']['stripped_instances'],{'BillboardGui':1,'Script':1,'Humanoid':1})
            self.assertEqual(validate(root/'job/render.png','item',size,r),r['png_sha256'])
            (assets.root/m['sha256']).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'digest'):assets.raw(m['id'])

    def test_xml_game_queue_with_gui_and_scripts_and_no_studio(self):
        data=b'<roblox version="4"><Item class="Workspace"><Item class="Part"><Properties><int name="BrickColor">21</int></Properties></Item><Item class="ScreenGui"><Item class="TextLabel"/></Item><Item class="Script"/></Item></roblox>'
        with tempfile.TemporaryDirectory() as d,patch('subprocess.Popen',side_effect=AssertionError('No subprocess')):
            renderer=Renderer(Path(d)/'ABSENT.exe',d,backend='custom')
            try:
                identity=renderer.upload(data);job=renderer.submit({'type':'game_thumbnail','place_id':identity,'size':{'width':128,'height':128}})
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    result=renderer.get(job)
                    if result['state'] not in ('queued','running'):break
                    time.sleep(.02)
                self.assertEqual(result['state'],'succeeded',result)
                self.assertEqual(result['result']['ignored_instances'],{'ScreenGui':1,'Script':1})
                self.assertTrue(renderer.image(result).startswith(b'\x89PNG'))
            finally:renderer.close()

    def test_unsupported_geometry_and_dtd_are_rejected(self):
        for data in [b'<!DOCTYPE a><roblox/>',b'<roblox><Item class="Terrain"/></roblox>',b'<roblox><Item class="Part"><Properties><token name="shape">0</token></Properties></Item></roblox>']:
            with self.assertRaises(ValueError):xml_scene(data)

if __name__=='__main__':unittest.main()
