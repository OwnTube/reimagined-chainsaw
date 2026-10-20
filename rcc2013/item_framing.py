"""Fit all eight item bounds corners with a consistent perspective margin."""
import math


def dot(a,b):return sum(x*y for x,y in zip(a,b))
def unit(v):
    length=math.sqrt(dot(v,v))
    return [x/length for x in v]


def item_camera(bounds, size):
    target=[(a+b)/2 for a,b in zip(bounds['min'],bounds['max'])]
    backward=unit([-.5,.3,-1])
    right=unit([-backward[2],0,backward[0]])
    up=[backward[1]*right[2]-backward[2]*right[1],
        backward[2]*right[0]-backward[0]*right[2],
        backward[0]*right[1]-backward[1]*right[0]]
    vertical=math.tan(math.radians(30)/2)
    horizontal=vertical*size['width']/size['height']
    distance=1
    for bits in range(8):
        point=[bounds['max' if bits&(1<<i) else 'min'][i]-target[i] for i in range(3)]
        distance=max(distance,dot(point,backward)+max(abs(dot(point,right))/horizontal,abs(dot(point,up))/vertical)*1.16)
    return {'position':[c+distance*v for c,v in zip(target,backward)],'target':target,'fov':30}
