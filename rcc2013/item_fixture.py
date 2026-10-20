"""Owned sword, mesh, and texture fixtures; no vendor assets are embedded."""
import io
import math
import struct
import xml.etree.ElementTree as ET
from PIL import Image


def texture():
    image=Image.new('RGB',(64,64),'white')
    for y in range(64):
        for x in range(32):image.putpixel((x,y),(8,8,8) if x<16 else (15,85,230))
    out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()


def mesh():
    outline=[(-.5,-2),(.5,-2),(.5,1.4),(0,2.3),(-.5,1.4)]
    front=[(x,y,-.12) for x,y in outline];back=[(x,y,.12) for x,y in outline]
    triangles=[]
    for i in range(1,4):
        triangles.append((front[0],front[i+1],front[i]));triangles.append((back[0],back[i],back[i+1]))
    for i in range(5):
        j=(i+1)%5
        triangles.extend(((front[i],front[j],back[i]),(front[j],back[j],back[i])))
    data=bytearray(b'version 2.00\n'+struct.pack('<HBBII',12,36,12,len(triangles)*3,len(triangles)))
    for triangle in triangles:
        a,b,c=triangle;u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        norm=math.sqrt(sum(x*x for x in n));n=[x/norm for x in n]
        for x,y,z in triangle:data.extend(struct.pack('<9f',x,y,z,*n,x+.5,(y+2)/4.3,0))
    for i in range(len(triangles)):data.extend(struct.pack('<III',i*3,i*3+1,i*3+2))
    return bytes(data)


def model(mesh_id, texture_id):
    root=ET.Element('roblox',version='4');tool=ET.SubElement(root,'Item',{'class':'Tool','referent':'RBX0'})
    props=ET.SubElement(tool,'Properties');ET.SubElement(props,'string',name='Name').text='RCC Practice Sword'
    def vector(parent,name,values):
        p=ET.SubElement(parent,'Vector3',name=name)
        for k,v in zip(('X','Y','Z'),values):ET.SubElement(p,k).text=str(v)
    def part(name,size,y,color):
        node=ET.SubElement(tool,'Item',{'class':'Part','referent':'RBX'+name});p=ET.SubElement(node,'Properties')
        ET.SubElement(p,'string',name='Name').text=name
        ET.SubElement(p,'int',name='BrickColor').text=str(color)
        vector(p,'size',size);cf=ET.SubElement(p,'CoordinateFrame',name='CFrame')
        for k,v in {'X':0,'Y':y,'Z':0,**{'R'+str(i)+str(j):int(i==j) for i in range(3) for j in range(3)}}.items():ET.SubElement(cf,k).text=str(v)
        return node
    part('Handle',(.7,2,.7),1.3,24);part('Guard',(3.4,.45,.8),2.5,21);part('Pommel',(1,.5,1),.2,23)
    blade=part('Blade',(1,4.3,.24),4.5,1001)
    m=ET.SubElement(blade,'Item',{'class':'SpecialMesh'});mp=ET.SubElement(m,'Properties')
    ET.SubElement(mp,'token',name='MeshType').text='5'
    for name,identity in [('MeshId',mesh_id),('TextureId',texture_id)]:
        ET.SubElement(ET.SubElement(mp,'Content',name=name),'url').text='rbxassetid://'+str(identity)
    vector(mp,'Scale',(1,1,1))
    gui=ET.SubElement(tool,'Item',{'class':'BillboardGui'});gp=ET.SubElement(gui,'Properties')
    ET.SubElement(gp,'string',name='Name').text='SHOULD_NOT_RENDER'
    label=ET.SubElement(gui,'Item',{'class':'TextLabel'});lp=ET.SubElement(label,'Properties')
    ET.SubElement(lp,'string',name='Text').text='SHOULD_NOT_RENDER'
    script=ET.SubElement(tool,'Item',{'class':'Script'});sp=ET.SubElement(script,'Properties')
    ET.SubElement(sp,'ProtectedString',name='Source').text='error("UNTRUSTED_SCRIPT_SHOULD_NOT_RUN")'
    ET.SubElement(tool,'Item',{'class':'Humanoid'})
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)
