import unittest

import numpy as np
from PIL import Image

from nailong_pet.imaging import (
    remove_connected_background,
    resize_transparent_image,
    to_colorkey_image,
)


class ImagingTests(unittest.TestCase):
    def test_opaque_magenta_is_not_confused_with_transparent_colorkey(self):
        image = Image.new("RGBA", (2, 1))
        image.putdata(((255, 0, 255, 255), (0, 0, 0, 0)))

        keyed = to_colorkey_image(image)

        self.assertEqual(keyed.getpixel((0, 0)), (254, 0, 255))
        self.assertEqual(keyed.getpixel((1, 0)), (255, 0, 255))

    def test_transparent_resize_outputs_rgb_colorkey_pixels(self):
        image = Image.new("RGBA", (4, 1))
        image.putdata(
            (
                (255, 255, 255, 255),
                (0, 0, 0, 0),
                (0, 0, 0, 0),
                (0, 0, 0, 0),
            )
        )

        resized = resize_transparent_image(image, (2, 1))

        self.assertEqual(resized.mode, "RGB")
        self.assertEqual(resized.getpixel((1, 0)), (255, 0, 255))
        self.assertEqual(resized.getpixel((0, 0)), (255, 255, 255))

    def test_background_removal_keeps_isolated_light_content(self):
        frame = np.full((5, 5, 3), 255, dtype=np.uint8)
        frame[1:4, 1:4] = (0, 180, 255)
        frame[2, 2] = (255, 255, 255)

        rgba = remove_connected_background(frame, chroma_tolerance=55)

        self.assertEqual(rgba[0, 0, 3], 0)
        self.assertEqual(rgba[2, 2, 3], 255)


if __name__ == "__main__":
    unittest.main()
