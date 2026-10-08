from contextlib import redirect_stderr
import io
import unittest

import app


class CommandLineTests(unittest.TestCase):
    def test_accepts_supported_rendering_values(self):
        arguments = app.parse_args(
            ["--width", "1080", "--display-width", "240", "--chroma-tolerance", "80"]
        )

        self.assertEqual(arguments.width, 1080)
        self.assertEqual(arguments.display_width, 240)
        self.assertEqual(arguments.chroma_tolerance, 80)

    def test_rejects_display_width_below_supported_minimum(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            app.parse_args(["--display-width", "59"])

    def test_rejects_invalid_chroma_tolerance(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            app.parse_args(["--chroma-tolerance", "256"])


if __name__ == "__main__":
    unittest.main()
