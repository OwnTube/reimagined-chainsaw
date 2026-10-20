"""Independent camera geometry using parameters observed in revival scripts.

The headshot preset follows BubbaBlox v2's no-hat R6 case: head-level eye,
three-stud distance, 11.25-degree side angle, 0.1-stud rearward target offset,
30-degree FOV. See docs/thumbnail-research.md for pinned source comparisons.
"""
import math


def revival_headshot(head_center=(0,4.5,0)):
    """Equivalent for our upright, unrotated classic head without accessories."""
    x,y,z=head_center
    side_angle=math.pi/16
    distance=3
    return {'position':[x+distance*math.sin(side_angle),y,z-distance*math.cos(side_angle)],
            'target':[x,y,z+0.1], 'fov':30}


HEADSHOT_CAMERA=revival_headshot()

# Fitted against the owner's 150x200 profile thumbnail using the bundled R6
# silhouette. A reconstruction from an image cannot uniquely recover the
# original camera. This is not ThumbnailGenerator's internal transform.
FULL_BODY_CAMERA={'position':[-2.44,5.06,-4.92], 'target':[0,2.5,0], 'fov':61}
