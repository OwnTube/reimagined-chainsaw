"""Fail closed before an avatar/item PNG is marked successful or delivered."""
import hashlib
from PIL import Image


def validate_png(path, render_type, size, report):
    with Image.open(path) as image:
        if image.format!='PNG':raise ValueError('Output is not a PNG')
        image.load()
        if size and image.size!=(size['width'],size['height']):raise ValueError('Output dimensions do not match the request')
        if render_type in ('headshot','full_body','item'):
            if image.mode!='RGBA':raise ValueError('Subject output must be RGBA')
            if not report.get('subject_gui_validated'):raise ValueError('Native subject GUI audit is missing')
            passes=report.get('passes',[])
            if len(passes)!=2 or not all(p.get('subject_gui_validated') and p.get('engine_render_validated') for p in passes):
                raise ValueError('Both native subject passes must validate')
            alpha=image.getchannel('A');hist=alpha.histogram()
            if hist[0]<100 or hist[255]<100:raise ValueError('Subject requires clear background and opaque geometry')
            w,h=image.size
            for x in list(range(3,11))+list(range(w-11,w-3)):
                for y in range(3,11):
                    if image.getpixel((x,y))!=(0,0,0,0):raise ValueError('Output retains background or obstructed corner patches')
            bounds=alpha.getbbox()
            if render_type in ('full_body','item') and min(bounds[0],bounds[1],w-bounds[2],h-bounds[3])<4:
                raise ValueError('Complete subject does not fit inside the output')
    return hashlib.sha256(path.read_bytes()).hexdigest()
