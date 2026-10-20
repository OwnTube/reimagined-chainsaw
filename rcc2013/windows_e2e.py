"""Validate game thumbnails, transparent full body, and transparent headshot."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from PIL import Image

from server import Renderer, handler, ThreadingHTTPServer
from item_fixture import model as item_model, mesh as item_mesh, texture as item_texture


def uploaded_place():
    root=ET.Element('roblox',version='4')
    ET.SubElement(root,'External').text='null'
    ET.SubElement(root,'External').text='nil'
    world=ET.SubElement(root,'Item',{'class':'Workspace','referent':'RBX0'})
    props=ET.SubElement(world,'Properties');ET.SubElement(props,'string',name='Name').text='Workspace'
    for i,(x,color) in enumerate(((-4,106),(4,24))):
        part=ET.SubElement(world,'Item',{'class':'Part','referent':'RBX'+str(i+1)})
        p=ET.SubElement(part,'Properties')
        ET.SubElement(p,'string',name='Name').text='UploadedBlock'+str(i)
        ET.SubElement(p,'bool',name='Anchored').text='true'
        ET.SubElement(p,'int',name='BrickColor').text=str(color)
        size=ET.SubElement(p,'Vector3',name='size')
        for k,v in zip(('X','Y','Z'),(5,7,5)):ET.SubElement(size,k).text=str(v)
        cf=ET.SubElement(p,'CoordinateFrame',name='CFrame')
        for k,v in {'X':x,'Y':3.5,'Z':0,'R00':1,'R01':0,'R02':0,'R10':0,'R11':1,'R12':0,'R20':0,'R21':0,'R22':1}.items():
            ET.SubElement(cf,k).text=str(v)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--studio',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('output'))
    args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    renderer=Renderer(args.studio,out/'data')
    http=ThreadingHTTPServer(('127.0.0.1',0),handler(renderer))
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(http.server_port)
    report={'native_engine_executed':True,'jobs':[]}
    def request(path,body=None):
        data=json.dumps(body).encode() if body is not None else None
        with urllib.request.urlopen(urllib.request.Request(base+path,data=data),timeout=10) as response:
            return json.load(response)
    try:
        report['health']=request('/health')
        place=uploaded_place()
        with urllib.request.urlopen(urllib.request.Request(base+'/v1/places',place,method='POST'),timeout=10) as response:
            place_id=json.load(response)['place_id']
        if place_id!=hashlib.sha256(place).hexdigest():raise RuntimeError('Upload digest differs')
        def upload_asset(kind,content):
            with urllib.request.urlopen(urllib.request.Request(base+'/v1/assets?kind='+kind,content,method='POST'),timeout=10) as response:return json.load(response)
        texture=upload_asset('texture',item_texture());mesh=upload_asset('mesh',item_mesh())
        item=upload_asset('model',item_model(mesh['id'],texture['id']))
        if item['metadata']['stripped_instances']!={'BillboardGui':1,'Script':1,'Humanoid':1}:raise RuntimeError('Active item content was not stripped')
        report['item_assets']={'texture':texture,'mesh':mesh,'model':item}
        for name,config in [('default',{'size':{'width':512,'height':512}}),
                            ('uploaded',{'place_id':place_id,'size':{'width':640,'height':360},
                                         'camera':{'position':[16,12,22],'target':[0,3,0],'fov':45}}),
                            ('full-body',{'type':'full_body','size':{'width':512,'height':512}}),
                            ('headshot',{'type':'headshot','size':{'width':512,'height':512}}),
                            ('full-body-reference',{'type':'full_body','size':{'width':450,'height':600}}),
                            ('item',{'type':'item','asset_id':item['id'],'size':{'width':512,'height':512}})]:
            job=request('/v1/renders',config)['id']
            deadline=time.monotonic()+100
            while time.monotonic()<deadline:
                result=request('/v1/renders/'+job)
                if result['state'] in ('succeeded','failed'):break
                time.sleep(0.5)
            report['jobs'].append(result)
            if result['state']!='succeeded':raise RuntimeError('Native render failed: '+json.dumps(result))
            with urllib.request.urlopen(base+'/v1/renders/'+job+'/image',timeout=10) as response:
                image=response.read()
                if response.headers.get_content_type()!='image/png' or not image.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise RuntimeError('Render API did not return a PNG')
            (out/(name+'-render.png')).write_bytes(image)
            if list(Image.open(io.BytesIO(image)).size)!=[config['size']['width'],config['size']['height']]:
                raise RuntimeError('Returned PNG does not match requested native image size')
            if config.get('type') in ('full_body','headshot'):
                if not result['result'].get('avatar_structure_validated') or not result['result'].get('avatar_gui_free'):
                    raise RuntimeError('R6 construction and GUI removal markers were not observed')
                if not result['result'].get('avatar_body_meshes_validated'):
                    raise RuntimeError('Dedicated 2013 body meshes were not confirmed')
                for native_pass in result['result']['passes']:
                    assets=native_pass.get('bundled_character_assets_sha256',{})
                    if len(assets)!=6 or 'character3.rbxm' not in assets:
                        raise RuntimeError('Native character template/mesh identities missing')
                decoded=Image.open(io.BytesIO(image))
                if decoded.mode!='RGBA' or decoded.getextrema()[3]!=(0,255):
                    raise RuntimeError('Player PNG must contain both transparent background and opaque player')
                if any(decoded.getpixel(p)[3]!=0 for p in ((0,0),(decoded.width-1,0))):
                    raise RuntimeError('Player thumbnail top corners must be fully transparent')
                if config['type']=='full_body':
                    x,y,r,b=decoded.getchannel('A').getbbox()
                    if min(x,y,decoded.width-r,decoded.height-b)<8:raise RuntimeError('Full body must fit inside the frame')
                    if name=='full-body-reference':
                        # Reference profile image is 150x200 with alpha bounds
                        # (16,12,147,171). Allow small mesh/AA differences.
                        expected=(48,36,441,513)
                        if max(abs(a-e) for a,e in zip((x,y,r,b),expected))>10:
                            raise RuntimeError('Native portrait silhouette does not match reference framing bounds')
                if name=='headshot':
                    camera=result['result']['camera']
                    if camera['fov']!=30 or camera['position'][1]!=4.5 or camera['target']!=[0,4.5,0.1]:
                        raise RuntimeError('Headshot did not use the source-referenced head-level camera')
                    for native_pass in result['result']['passes']:
                        if not any('|CAMERA_READY|' in line and '|fov=30' in line for line in native_pass['engine_marker_lines']):
                            raise RuntimeError('Native headshot camera marker did not confirm the preset')
            if name=='item':
                native=result['result']
                if not all(native.get(k) for k in ('item_structure_validated','asset_delivery_validated','subject_gui_validated','transparent')):
                    raise RuntimeError('Native item structure, delivery, GUI, or alpha proof missing')
                colors={'black':0,'white':0,'blue':0}
                for r,g,b,a in Image.open(io.BytesIO(image)).getdata():
                    if a==255:
                        colors['black']+=max(r,g,b)<45
                        colors['white']+=min(r,g,b)>120 and max(r,g,b)-min(r,g,b)<40
                        colors['blue']+=b>80 and b>r*1.5 and b>g*1.2
                if min(colors.values())<100:raise RuntimeError('Delivered mesh texture was not visibly rendered with black, white, and blue pixels')
                report['item_texture_pixels']=colors
        report['two_distinct_images']=report['jobs'][0]['result']['png_sha256']!=report['jobs'][1]['result']['png_sha256']
        if not report['two_distinct_images']:raise RuntimeError('Distinct scenes produced the same image')
        if report['jobs'][2]['result']['png_sha256']==report['jobs'][3]['result']['png_sha256']:
            raise RuntimeError('Full body and headshot must be different images')
        report['passed']=True
    finally:
        http.shutdown();http.server_close();renderer.close();thread.join(timeout=5)
        (out/'api-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
