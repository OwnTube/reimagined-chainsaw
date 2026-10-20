"""Original CPU triangle renderer. No Studio, Roblox process, Lua, or GUI.

Lighting is our Lambert approximation; original 2013 engine parity is unproved.
Only static Block Parts and local version-2 meshes are currently implemented.
"""
from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import time
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from assets import mesh_metadata, vector, REMOVE

COLORS={1:(242,243,243),21:(196,40,28),23:(13,105,172),24:(245,205,48),26:(27,42,53),28:(40,127,71),37:(75,151,75),194:(163,162,165),199:(99,95,98),1001:(248,248,248)}

@dataclass
class Mesh:
    vertices: object
    normals: object
    uv: object
    triangles: object
    color: tuple
    texture: object=None

def read_mesh(data,color=(255,255,255)):
    mesh_metadata(data)
    start=len(b'version 2.00\n');header,stride,_,vertices,faces=struct.unpack_from('<HBBII',data,start)
    rows=np.ndarray((vertices,9),dtype='<f4',buffer=data,offset=start+header,strides=(stride,4)).astype(float)
    indices=np.frombuffer(data,dtype='<u4',count=faces*3,offset=start+header+vertices*stride).reshape(-1,3).copy()
    return Mesh(rows[:,:3],rows[:,3:6],rows[:,6:8],indices,color)

def cube(size,color):
    points=[];normals=[];uv=[];faces=[]
    for axis in range(3):
        other=[i for i in range(3) if i!=axis]
        for sign in (-1,1):
            start=len(points)
            for a,b in ((-1,-1),(1,-1),(1,1),(-1,1)):
                p=[0.,0.,0.];p[axis]=sign*size[axis]/2;p[other[0]]=a*size[other[0]]/2;p[other[1]]=b*size[other[1]]/2
                n=[0.,0.,0.];n[axis]=sign;points.append(p);normals.append(n);uv.append([(a+1)/2,(b+1)/2])
            faces.extend([[start,start+1,start+2],[start,start+2,start+3]])
    return Mesh(np.array(points),np.array(normals),np.array(uv),np.array(faces),color)

def transform(mesh,position,rotation=None,scale=(1,1,1)):
    rotation=np.eye(3) if rotation is None else np.asarray(rotation,float);scale=np.asarray(scale,float)
    if np.any(np.abs(scale)<1e-8):raise ValueError('Degenerate mesh scale')
    mesh.vertices=(mesh.vertices*scale)@rotation.T+position
    mesh.normals=(mesh.normals/scale)@rotation.T;mesh.normals/=np.maximum(np.linalg.norm(mesh.normals,axis=1)[:,None],1e-10)
    return mesh

def avatar(content):
    content=Path(content);meshes=[];manifest=[]
    specs=[('head',(0,4.5,0),24),('torso',(0,3,0),23),('leftarm',(-1.5,3,0),24),('rightarm',(1.5,3,0),24),('leftleg',(-.5,1,0),37),('rightleg',(.5,1,0),37)]
    for name,position,color in specs:
        path=content/'fonts'/(name+'.mesh');data=path.read_bytes();meshes.append(transform(read_mesh(data,COLORS[color]),position))
        manifest.append({'asset':str(path.relative_to(content)),'sha256':hashlib.sha256(data).hexdigest()})
    data=(content/'textures/face.png').read_bytes();texture=np.array(Image.open(io.BytesIO(data)).convert('RGBA'))
    front=float(meshes[0].vertices[:,2].min())-.002
    meshes.append(Mesh(np.array([[-.5,4,front],[.5,4,front],[.5,5,front],[-.5,5,front]]),np.array([[0.,0.,-1.]]*4),np.array([[0,1],[1,1],[1,0],[0,0]]),np.array([[0,1,2],[0,2,3]]),(255,255,255),texture))
    manifest.append({'asset':'textures/face.png','sha256':hashlib.sha256(data).hexdigest()})
    return meshes,manifest

def blocks():
    specs=[((0,-1,0),(32,2,28),194),((-6,2,0),(4,6,4),21),((0,1,0),(4,4,4),23),((6,3,0),(4,8,4),24)]
    return [transform(cube(size,COLORS[color]),position) for position,size,color in specs]

def xml_scene(data,assets=None):
    if len(data)>8*1024*1024 or b'<!' in data:raise ValueError('Invalid/excessive XML or DTD')
    try:root=ET.fromstring(data)
    except ET.ParseError:raise ValueError('Custom renderer requires XML models/places')
    if root.tag!='roblox' or len(list(root.iter()))>20000:raise ValueError('Invalid/excessive scene')
    meshes=[];manifest=[];ignored={}
    def dependency(raw,kind):
        if not raw.startswith('rccasset://') or not assets:raise ValueError('Only uploaded local dependencies are supported')
        identity=int(raw.split('://')[1]);info=assets.info(identity)
        if not info or info['kind']!=kind:raise ValueError('Missing local '+kind)
        body=assets.raw(identity);manifest.append({'asset_id':identity,'kind':kind,'sha256':hashlib.sha256(body).hexdigest()});return body
    def walk(item,depth=0):
        if depth>32:raise ValueError('Scene nesting too deep')
        kind=item.get('class','')
        if kind in REMOVE or kind.endswith('Gui'):ignored[kind]=ignored.get(kind,0)+1;return
        if kind in {'Model','Tool','Hat','Accoutrement','Workspace','DataModel','Folder'}:
            for child in item.findall('Item'):walk(child,depth+1)
            return
        if kind!='Part':raise ValueError('Custom renderer does not yet support '+kind)
        if len(meshes)>=256:raise ValueError('Too many parts')
        props={p.get('name'):p for p in item.findall('./Properties/*')}
        number=lambda key,default:float(props[key].text) if key in props else default
        opacity=1-number('Transparency',0)
        if not math.isfinite(opacity) or not 0<=opacity<=1:raise ValueError('Invalid opacity')
        if opacity==0:return
        if opacity!=1:raise ValueError('Partial Part transparency is not implemented')
        if number('shape',number('Shape',1))!=1:raise ValueError('Only Block shapes are implemented')
        size=vector(props.get('size',props.get('Size')),(2,2,2))
        if min(size)<=0:raise ValueError('Invalid size')
        cf=props.get('CFrame');position=vector(cf,(0,0,0))
        rotation=np.eye(3) if cf is None else np.array([[float(cf.findtext('R'+str(i)+str(j))) for j in range(3)] for i in range(3)])
        if not np.isfinite(rotation).all() or not np.allclose(rotation@rotation.T,np.eye(3),atol=.01):raise ValueError('Invalid rotation')
        color=int(number('BrickColor',194))
        if color not in COLORS:raise ValueError('Unsupported BrickColor '+str(color))
        mesh=cube(size,COLORS[color]);scale=(1,1,1);offset=(0,0,0)
        for child in item.findall('Item'):
            ck=child.get('class','');cp={p.get('name'):p for p in child.findall('./Properties/*')}
            if ck=='SpecialMesh':
                raw=cp.get('MeshId');raw=raw.findtext('url','') if raw is not None else ''
                mesh=read_mesh(dependency(raw,'mesh'),COLORS[color]);scale=vector(cp.get('Scale'),(1,1,1));offset=vector(cp.get('Offset'),(0,0,0))
                tex=cp.get('TextureId');tex=tex.findtext('url','') if tex is not None else ''
                if tex:mesh.texture=np.array(Image.open(io.BytesIO(dependency(tex,'texture'))).convert('RGBA'))
            elif ck in REMOVE or ck.endswith('Gui'):ignored[ck]=ignored.get(ck,0)+1
            else:raise ValueError('Unsupported visual child '+ck)
        meshes.append(transform(mesh,np.asarray(position)+rotation@np.asarray(offset),rotation,scale))
    for item in root.findall('Item'):walk(item)
    if not meshes:raise ValueError('No supported visible geometry')
    return meshes,manifest,ignored

def rasterize(meshes,camera,size,transparent=True,supersample=2):
    width=size['width']*supersample;height=size['height']*supersample
    eye=np.array(camera['position'],float);forward=np.array(camera['target'],float)-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,1,0]);length=np.linalg.norm(right)
    if length<1e-8:raise ValueError('Degenerate camera up axis')
    right/=length;view=np.stack([right,np.cross(right,forward),forward],axis=1);focal=height/(2*math.tan(math.radians(camera['fov'])/2))
    color=np.zeros((height,width,4),float)
    if not transparent:color[:]=[164,191,214,255]
    depth=np.full((height,width),np.inf);light=np.array([-.4,.8,-.65]);light/=np.linalg.norm(light);triangles=fragments=0
    for mesh in meshes:
        vertices=(mesh.vertices-eye)@view
        if np.any(vertices[:,2]<=.01):raise ValueError('Near-plane clipping is not implemented; adjust camera')
        projected=np.stack([vertices[:,0]*focal/vertices[:,2]+width/2,height/2-vertices[:,1]*focal/vertices[:,2]],axis=1);lighting=np.clip(.58+.42*(mesh.normals@light),.35,1)
        for face in mesh.triangles:
            p=projected[face];z=vertices[face,2];lo=np.maximum(np.floor(p.min(axis=0)).astype(int),[0,0]);hi=np.minimum(np.ceil(p.max(axis=0)).astype(int),[width-1,height-1])
            if np.any(lo>hi):continue
            a,b,c=p;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-10:continue
            y,x=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1];x=x+.5;y=y+.5
            w0=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den;w1=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den
            bary=np.stack([w0,w1,1-w0-w1],axis=-1);inv=(bary/z).sum(axis=-1);pixel_z=1/np.maximum(inv,1e-12);slab=np.s_[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
            mask=(bary.min(axis=-1)>=-1e-7)&(pixel_z<depth[slab])
            if not mask.any():continue
            perspective=bary/z/inv[...,None];shade=perspective@lighting[face];rgb=np.broadcast_to(np.array(mesh.color,float),(*shade.shape,3)).copy();alpha=np.full(shade.shape,255.)
            if mesh.texture is not None:
                uv=np.clip(perspective@mesh.uv[face],0,1);th,tw=mesh.texture.shape[:2];pixels=mesh.texture[np.minimum((uv[...,1]*th).astype(int),th-1),np.minimum((uv[...,0]*tw).astype(int),tw-1)]
                rgb*=pixels[...,:3]/255;alpha=pixels[...,3].astype(float);mask&=alpha>0
            old=color[slab];a=alpha[...,None]/255;out_a=a+old[...,3:4]/255*(1-a)
            rgb=(rgb*shade[...,None]*a+old[...,:3]*old[...,3:4]/255*(1-a))/np.maximum(out_a,1e-9)
            blended=np.concatenate([rgb,out_a*255],axis=-1);color[slab][mask]=blended[mask];depth[slab][mask]=pixel_z[mask];fragments+=int(mask.sum());triangles+=1
    image=Image.fromarray(np.clip(np.rint(color),0,255).astype('uint8'),'RGBA')
    if supersample!=1:image=image.resize((size['width'],size['height']),Image.Resampling.LANCZOS)
    rgba=np.array(image);rgba[rgba[:,:,3]==0,:3]=0
    return Image.fromarray(rgba,'RGBA'),{'triangles_rasterized':triangles,'depth_fragments':fragments,'supersample':supersample}

def validate(path,render_type,size,report):
    with Image.open(path) as image:
        image.load()
        if image.format!='PNG' or image.mode!='RGBA' or image.size!=(size['width'],size['height']):raise ValueError('Custom output dimensions/format invalid')
        rgba=np.array(image);alpha=rgba[:,:,3]
    if report.get('backend')!='custom_software' or report.get('studio_launched') is not False or report.get('gui_objects_created')!=0:raise ValueError('Custom renderer/GUI proof missing')
    if not (alpha==255).any():raise ValueError('No opaque subject pixels')
    if render_type!='game_thumbnail':
        if np.count_nonzero(alpha==0)<100 or np.any(rgba[alpha==0,:3]):raise ValueError('Invalid transparent background')
        if render_type=='headshot' and alpha[:3].any():raise ValueError('Head touches top border')
        if render_type in ('full_body','item') and (alpha[:3].any() or alpha[-3:].any() or alpha[:,:3].any() or alpha[:,-3:].any()):raise ValueError('Subject touches border')
    elif np.any(alpha!=255):raise ValueError('Game thumbnail must be opaque')
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def render(content,output,place,camera,size,scene,render_type,assets=None,asset_id=None):
    start=time.monotonic();output=Path(output);output.mkdir(parents=True,exist_ok=False);size=size or {'width':640,'height':480};manifest=[];ignored={}
    if render_type in ('headshot','full_body'):meshes,manifest=avatar(content)
    elif render_type=='item':meshes,manifest,ignored=xml_scene(assets.raw(asset_id),assets)
    elif place:meshes,manifest,ignored=xml_scene(Path(place).read_bytes(),assets)
    else:meshes=blocks()
    image,statistics=rasterize(meshes,camera,size,render_type!='game_thumbnail');temporary=output/'render.pending.png';image.save(temporary)
    report={'backend':'custom_software','renderer':'original CPU triangle rasterizer','type':render_type,'image_size':[size['width'],size['height']],'camera':camera,'studio_launched':False,'gui_objects_created':0,'custom_render_validated':False,'engine_render_validated':False,'original_2013_engine_parity_verified':False,'transparent':render_type!='game_thumbnail','assets':manifest,'ignored_instances':ignored,'statistics':statistics,'meshes':len(meshes),'seconds':round(time.monotonic()-start,3)}
    report['png_sha256']=validate(temporary,render_type,size,report);temporary.replace(output/'render.png');report['custom_render_validated']=True
    (output/'custom-render.json').write_text(json.dumps(report,indent=2)+'\n');return report
