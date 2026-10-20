"""Local immutable asset delivery for bounded static 2013 item models."""
from collections import Counter
from contextlib import contextmanager
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sqlite3
import struct
import threading
import uuid
import xml.etree.ElementTree as ET
from PIL import Image

LIMIT=8*1024*1024
CONTAINERS={'Model','Tool','Hat','Accoutrement'}
PARTS={'Part','WedgePart','CornerWedgePart'}
MESHES={'SpecialMesh','BlockMesh','CylinderMesh'}
VISUALS=PARTS|MESHES|{'Decal','Texture'}
REMOVE={'Script','LocalScript','ModuleScript','Humanoid','AnimationController',
        'BillboardGui','SurfaceGui','ScreenGui','Frame','TextLabel','TextButton',
        'TextBox','ImageLabel','ImageButton','ScrollingFrame','GuiMain',
        'Motor6D','Motor','Weld','ManualWeld','Snap','Sound','ClickDetector',
        'TouchTransmitter','Fire','Smoke','Sparkles','PointLight','SpotLight'}
PROPERTIES={'Name','size','Size','CFrame','BrickColor','Transparency','Reflectance',
            'Shape','shape','FormFactor','formFactor','TopSurface','BottomSurface',
            'MeshType','MeshId','TextureId','Scale','Offset','VertexColor','Texture',
            'Face','StudsPerTileU','StudsPerTileV'}


def vector(element, default):
    if element is None:return list(default)
    try:values=[float(element.findtext(k)) for k in ('X','Y','Z')]
    except (TypeError,ValueError):raise ValueError('Invalid model vector')
    if any(not math.isfinite(v) or abs(v)>4096 for v in values):raise ValueError('Model vector outside supported bounds')
    return values


def mesh_metadata(data):
    if not data.startswith(b'version 2.00\n'):raise ValueError('Only version 2.00 meshes are supported')
    start=len(b'version 2.00\n')
    try:header,stride,face_stride,vertices,faces=struct.unpack_from('<HBBII',data,start)
    except struct.error:raise ValueError('Truncated mesh header')
    if header!=12 or stride not in (36,40) or face_stride!=12 or not 3<=vertices<=100000 or not 1<=faces<=200000:
        raise ValueError('Unsupported mesh layout or count')
    if len(data)!=start+header+stride*vertices+12*faces:raise ValueError('Mesh length does not match header')
    low=[math.inf]*3;high=[-math.inf]*3
    for i in range(vertices):
        values=struct.unpack_from('<9f',data,start+header+i*stride)
        if any(not math.isfinite(v) or abs(v)>10000 for v in values):raise ValueError('Invalid mesh vertex')
        for axis,value in enumerate(values[:3]):
            if abs(value)>256:raise ValueError('Mesh geometry exceeds supported bounds')
            low[axis]=min(low[axis],value);high[axis]=max(high[axis],value)
    for i in range(faces):
        if max(struct.unpack_from('<III',data,start+header+stride*vertices+i*12))>=vertices:
            raise ValueError('Mesh triangle references an absent vertex')
    return {'bounds':{'min':low,'max':high},'vertices':vertices,'faces':faces}


def sanitize_model(data, lookup):
    if b'<!' in data:raise ValueError('DTD/entity declarations are unsupported')
    try:original=ET.fromstring(data)
    except ET.ParseError:raise ValueError('Expected a Roblox XML model (.rbxmx)')
    if original.tag!='roblox' or len(list(original.iter()))>10000:raise ValueError('Invalid or excessive XML model')
    stripped=Counter();dependencies=set();parts=[];nodes=0
    root=ET.Element('roblox',version='4')
    ET.SubElement(root,'External').text='null';ET.SubElement(root,'External').text='nil'

    def copy(item, parent, depth=0):
        nonlocal nodes
        if depth>32:raise ValueError('Model nesting exceeds supported depth')
        kind=item.get('class','')
        if kind in REMOVE or kind.endswith('Gui'):
            stripped[kind]+=1;return
        if kind not in CONTAINERS|VISUALS:raise ValueError('Unsupported static item class: '+kind)
        nodes+=1
        if nodes>2048:raise ValueError('Too many item instances')
        out=ET.SubElement(parent,'Item',{'class':kind,'referent':'RBX'+str(nodes)})
        props=ET.SubElement(out,'Properties')
        seen=set()
        for prop in item.findall('./Properties/*'):
            name=prop.get('name','')
            if name not in PROPERTIES:continue
            if name in seen:raise ValueError('Duplicate model property: '+name)
            seen.add(name)
            if prop.tag in ('ProtectedString','BinaryString','Ref'):raise ValueError('Unsupported property encoding')
            value=ET.fromstring(ET.tostring(prop))
            if name=='Name':
                if prop.tag!='string' or len(prop.text or '')>128:raise ValueError('Invalid item name')
            elif name in ('MeshId','TextureId','Texture'):
                raw=prop.findtext('url') or ''
                if raw:
                    match=re.fullmatch(r'(?:rbxassetid|rccasset)://([1-9][0-9]{0,9})',raw)
                    if not match:raise ValueError('Item dependencies must reference uploaded local asset IDs')
                    identity=int(match[1]);dependency=lookup(identity)
                    expected='mesh' if name=='MeshId' else 'texture'
                    if not dependency or dependency['kind']!=expected:raise ValueError('Missing or mismatched '+expected+' dependency')
                    dependencies.add(identity)
                    value=ET.Element('Content',name=name);ET.SubElement(value,'url').text='rccasset://'+str(identity)
                else:value=ET.Element('Content',name=name);ET.SubElement(value,'null')
            elif prop.tag=='Vector3':vector(prop,(0,0,0))
            elif prop.tag=='CoordinateFrame':
                expected=('X','Y','Z','R00','R01','R02','R10','R11','R12','R20','R21','R22')
                try:values=[float(prop.findtext(k)) for k in expected]
                except (TypeError,ValueError):raise ValueError('Invalid item CFrame')
                if any(not math.isfinite(v) or abs(v)>4096 for v in values):raise ValueError('Invalid item CFrame')
                rotation=values[3:]
                for a in range(3):
                    for b in range(3):
                        dot=sum(rotation[a*3+k]*rotation[b*3+k] for k in range(3))
                        if abs(dot-(1 if a==b else 0))>0.01:raise ValueError('Item rotation must be orthonormal')
            elif prop.tag in ('float','double','int','token'):
                try:number=float(prop.text)
                except (ValueError,TypeError):raise ValueError('Invalid item property number')
                if not math.isfinite(number) or abs(number)>1000000:raise ValueError('Invalid item property number')
                if name in ('Transparency','Reflectance') and not 0<=number<=1:raise ValueError('Invalid item opacity/reflectance')
            else:raise ValueError('Unsupported item property type: '+prop.tag)
            props.append(value)
        if kind in PARTS:
            if len(parts)>=256:raise ValueError('Too many item parts')
            for name in ('Anchored','CanCollide'):
                ET.SubElement(props,'bool',name=name).text='true' if name=='Anchored' else 'false'
            for child in list(props):
                if child.get('name','').lower()=='formfactor':props.remove(child)
            ET.SubElement(props,'token',name='formFactor').text='3'
            parts.append(out)
        for child in item.findall('Item'):copy(child,out,depth+1)

    for item in original.findall('Item'):copy(item,root)
    if len(root.findall('Item'))!=1:raise ValueError('An item requires exactly one root instance')
    if not parts:raise ValueError('Item has no supported geometry')
    low=[math.inf]*3;high=[-math.inf]*3;visible=0
    for part in parts:
        props=part.find('Properties')
        if float(props.findtext('float[@name="Transparency"]','0'))>=1:continue
        visible+=1
        size=vector(props.find('Vector3[@name="size"]'),(2,2,2))
        if props.find('Vector3[@name="Size"]') is not None:size=vector(props.find('Vector3[@name="Size"]'),size)
        if any(not 0.05<=v<=256 for v in size):raise ValueError('Unsupported item part size')
        bounds={'min':[-v/2 for v in size],'max':[v/2 for v in size]}
        mesh=next((child for child in part.findall('Item') if child.get('class') in MESHES),None)
        if mesh is not None:
            mp=mesh.find('Properties');scale=vector(mp.find('Vector3[@name="Scale"]'),(1,1,1));offset=vector(mp.find('Vector3[@name="Offset"]'),(0,0,0))
            url=mp.findtext('Content[@name="MeshId"]/url','')
            if url:bounds=lookup(int(url.split('://')[1]))['metadata']['bounds']
            bounds={key:[v*s+o for v,s,o in zip(bounds[key],scale,offset)] for key in ('min','max')}
        cf=props.find('CoordinateFrame[@name="CFrame"]')
        position=vector(cf,(0,0,0))
        rotation=[float(cf.findtext('R'+str(a)+str(b))) if cf is not None else float(a==b) for a in range(3) for b in range(3)]
        for bits in range(8):
            point=[bounds['max' if bits&(1<<axis) else 'min'][axis] for axis in range(3)]
            for axis in range(3):
                value=position[axis]+sum(rotation[axis*3+k]*point[k] for k in range(3))
                low[axis]=min(low[axis],value);high[axis]=max(high[axis],value)
    if not visible or max(high[i]-low[i] for i in range(3))>512:raise ValueError('Item bounds are empty or excessive')
    canonical=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    return canonical,{'parts':len(parts),'visible_parts':visible,'bounds':{'min':low,'max':high},
                      'dependencies':sorted(dependencies),'stripped_instances':dict(stripped),
                      'sanitizer':'static XML geometry allowlist; scripts, GUI, Humanoids and joints removed'}


class AssetStore:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.deliveries=[];self.sequence=0
        with self.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS assets (id INTEGER PRIMARY KEY AUTOINCREMENT, sha TEXT UNIQUE, kind TEXT, mime TEXT, metadata TEXT)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.root/'assets.sqlite3',timeout=15)
        try:
            with db:yield db
        finally:db.close()

    def info(self, identity):
        with self.connect() as db:row=db.execute('SELECT id,sha,kind,mime,metadata FROM assets WHERE id=?',(identity,)).fetchone()
        return dict(zip(('id','sha256','kind','mime','metadata'),(*row[:4],json.loads(row[4])))) if row else None

    def upload(self, kind, data):
        if not 0<len(data)<=LIMIT:raise ValueError('Asset must be 1 byte..8 MiB')
        if kind=='model':data,metadata=sanitize_model(data,self.info);mime='application/octet-stream'
        elif kind=='mesh':metadata=mesh_metadata(data);mime='application/octet-stream'
        elif kind=='texture':
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Texture must be a PNG')
            try:
                with Image.open(io.BytesIO(data)) as image:
                    if image.format!='PNG' or max(image.size)>4096:raise ValueError('Texture exceeds 4096 pixels')
                    metadata={'size':list(image.size)};image.verify()
            except (OSError,Image.DecompressionBombError) as error:raise ValueError('Invalid texture PNG') from error
            mime='image/png'
        else:raise ValueError('Asset kind must be model, mesh, or texture')
        digest=hashlib.sha256(data).hexdigest()
        with self.lock,self.connect() as db:
            path=self.root/digest
            if not path.exists():
                temporary=self.root/(uuid.uuid4().hex+'.tmp');temporary.write_bytes(data);temporary.replace(path)
            db.execute('INSERT OR IGNORE INTO assets (sha,kind,mime,metadata) VALUES (?,?,?,?)',(digest,kind,mime,json.dumps(metadata)))
            identity=db.execute('SELECT id FROM assets WHERE sha=?',(digest,)).fetchone()[0]
        return self.info(identity)

    def raw(self, identity):
        info=self.info(identity)
        if info is None:raise KeyError(identity)
        data=(self.root/info['sha256']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=info['sha256']:raise ValueError('Stored asset digest mismatch')
        return data

    def content(self, identity, base):
        info=self.info(identity)
        if info is None:raise KeyError(identity)
        data=self.raw(identity)
        if info['kind']=='model':
            data=re.sub(rb'rccasset://([1-9][0-9]*)',lambda m:(base+'/assets/'+m[1].decode()+'/content').encode(),data)
        digest=hashlib.sha256(data).hexdigest()
        with self.lock:
            self.sequence+=1
            self.deliveries.append({'sequence':self.sequence,'id':identity,'kind':info['kind'],'sha256':digest})
            self.deliveries=self.deliveries[-1024:]
        return data,info,digest

    def trace(self, after):
        with self.lock:return [dict(x) for x in self.deliveries if x['sequence']>after]
