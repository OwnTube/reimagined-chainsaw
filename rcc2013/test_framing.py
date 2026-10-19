import math
import unittest
from framing import revival_headshot


class FramingTests(unittest.TestCase):
    def test_headshot_eye_is_level_three_studs_away_and_uses_revival_yaw(self):
        camera=revival_headshot()
        x,y,z=camera['position']
        self.assertEqual(y,4.5)
        self.assertAlmostEqual(math.hypot(x,z),3)
        self.assertAlmostEqual(math.degrees(math.atan2(x,-z)),11.25)
        self.assertEqual(camera['target'],[0,4.5,0.1])
        self.assertEqual(camera['fov'],30)

    def test_headshot_tracks_head_translation_instead_of_world_height(self):
        original=revival_headshot()
        shifted=revival_headshot((12,24.5,-8))
        for field in ('position','target'):
            for actual,base,offset in zip(shifted[field],original[field],(12,20,-8)):
                self.assertAlmostEqual(actual,base+offset)


if __name__=='__main__':unittest.main()
