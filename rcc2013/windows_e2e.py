"""Exercise the actual HTTP API and two real native 2013 rendering jobs."""
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
        for name,config in [('default',{'size':{'width':512,'height':512}}),
                            ('uploaded',{'place_id':place_id,'size':{'width':640,'height':360},
                                         'camera':{'position':[16,12,22],'target':[0,3,0],'fov':45}})]:
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
        report['two_distinct_images']=report['jobs'][0]['result']['png_sha256']!=report['jobs'][1]['result']['png_sha256']
        if not report['two_distinct_images']:raise RuntimeError('Distinct scenes produced the same image')
        report['passed']=True
    finally:
        http.shutdown();http.server_close();renderer.close();thread.join(timeout=5)
        (out/'api-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
