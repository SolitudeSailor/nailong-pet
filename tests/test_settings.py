import unittest

from nailong_pet.settings import PetSettings


class PetSettingsTests(unittest.TestCase):
    def test_from_mapping_validates_and_normalizes_values(self):
        settings = PetSettings.from_mapping(
            {
                "width": 900,
                "position": [-120, 80],
                "sound": False,
                "volume": -10,
                "idle": True,
                "snap": False,
            },
            default_width=180,
        )

        self.assertEqual(settings.width, 720)
        self.assertEqual(settings.position, (-120, 80))
        self.assertFalse(settings.sound)
        self.assertEqual(settings.volume, 0)
        self.assertTrue(settings.idle)
        self.assertFalse(settings.snap)

    def test_invalid_types_fall_back_to_defaults(self):
        settings = PetSettings.from_mapping(
            {
                "width": "wide",
                "position": [True, 10],
                "sound": "yes",
                "volume": None,
                "idle": 1,
                "snap": [],
            },
            default_width=240,
        )

        self.assertEqual(settings, PetSettings(width=240))

    def test_to_mapping_uses_json_compatible_position(self):
        settings = PetSettings(width=240, position=(-100, 50), sound=False)

        self.assertEqual(
            settings.to_mapping(),
            {
                "width": 240,
                "position": [-100, 50],
                "sound": False,
                "volume": 70,
                "idle": False,
                "snap": True,
            },
        )


if __name__ == "__main__":
    unittest.main()
