"""Recover straight RGBA from two registered native frames, not color-key removal."""
from collections import Counter
from statistics import median
from PIL import Image


def recover_alpha(dark, light):
    dark, light = dark.convert('RGB'), light.convert('RGB')
    if dark.size != light.size:
        raise ValueError('Matte frames must have identical dimensions')
    # The planar backdrop fills both upper corner patches. A headshot may
    # legitimately crop the shoulders at the bottom, so do not sample there.
    width,height = dark.size
    if min(width,height)<16:
        raise ValueError('Matte frames are too small for background calibration')
    points = [(x,y) for y in range(3,11) for x in list(range(3,11))+list(range(width-11,width-3))]
    bases=[]
    for image in (dark,light):
        samples=[image.getpixel(p) for p in points]
        base=tuple(int(median(p[c] for p in samples)) for c in range(3))
        if max(abs(p[c]-base[c]) for p in samples for c in range(3))>3:
            raise ValueError('Backdrop corner patches are not uniform and unobstructed')
        bases.append(base)
    low,high=bases
    delta=[high[c]-low[c] for c in range(3)]
    if min(delta)<80:
        raise ValueError('Native backdrop contrast is insufficient for alpha recovery')
    pixels=[]
    residuals=[]
    counts=Counter()
    for a,b in zip(dark.getdata(),light.getdata()):
        alpha=max(0.0,min(1.0,1-median((b[c]-a[c])/delta[c] for c in range(3))))
        if alpha<0.01:alpha=0.0
        if alpha>0.99:alpha=1.0
        if alpha==0:
            color=(0,0,0)
        else:
            color=tuple(round(max(0,min(255,(a[c]-(1-alpha)*low[c])/alpha))) for c in range(3))
        byte=round(alpha*255)
        pixels.append((*color,byte))
        counts['transparent' if byte==0 else 'opaque' if byte==255 else 'partial']+=1
        residuals.append(max(abs((b[c]-a[c])-(1-alpha)*delta[c]) for c in range(3)))
    image=Image.new('RGBA',dark.size);image.putdata(pixels)
    p99=sorted(residuals)[int((len(residuals)-1)*0.99)]
    if p99>8:
        raise ValueError('Matte passes disagree: camera, geometry, or foreground lighting changed')
    return image,{'method':'two native solid-backdrop passes with calibrated straight-alpha recovery',
                  'background_rgb':[list(low),list(high)],'alpha_counts':dict(counts),
                  'registration_residual_p99':round(p99,3)}
