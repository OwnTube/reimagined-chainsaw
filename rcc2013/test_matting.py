import unittest
from PIL import Image
from matting import recover_alpha


class MattingTests(unittest.TestCase):
    def test_recovers_edges_and_preserves_black_white_and_blue_foreground(self):
        frames=[Image.new('RGB',(64,64),v) for v in ((12,12,12),(232,232,232))]
        samples=[((0,0,0),1),((255,255,255),1),((0,80,220),1),((30,140,220),0.5)]
        for i,(color,alpha) in enumerate(samples):
            for frame,background in zip(frames,(12,232)):
                rgb=tuple(round(alpha*c+(1-alpha)*background) for c in color)
                for y in range(20,44):
                    for x in range(16+i*8,24+i*8):frame.putpixel((x,y),rgb)
        result,stats=recover_alpha(*frames)
        self.assertEqual(result.getpixel((0,0)),(0,0,0,0))
        for i,(color,alpha) in enumerate(samples):
            pixel=result.getpixel((18+i*8,30))
            self.assertLessEqual(abs(pixel[3]-round(alpha*255)),1)
            self.assertTrue(all(abs(a-b)<=2 for a,b in zip(pixel[:3],color)))
        self.assertGreater(stats['alpha_counts']['transparent'],0)
        self.assertGreater(stats['alpha_counts']['partial'],0)

    def test_rejects_unregistered_or_low_contrast_frames(self):
        with self.assertRaises(ValueError):recover_alpha(Image.new('RGB',(32,32)),Image.new('RGB',(64,64)))
        with self.assertRaises(ValueError):recover_alpha(Image.new('RGB',(32,32)),Image.new('RGB',(32,32)))

    def test_small_native_shading_differences_do_not_make_opaque_skin_translucent(self):
        dark=Image.new('RGB',(64,64),(11,11,11))
        light=Image.new('RGB',(64,64),(132,132,132))
        for y in range(20,44):
            for x in range(20,44):
                dark.putpixel((x,y),(130,110,25))
                light.putpixel((x,y),(133,113,28))
        image,_=recover_alpha(dark,light)
        self.assertEqual(image.getpixel((30,30))[3],255)
        self.assertEqual(image.getpixel((0,0))[3],0)


if __name__=='__main__':unittest.main()
