from pathlib import Path
import re
import unittest

from nailong_pet import APP_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PackagingNameTests(unittest.TestCase):
    def test_build_uses_chinese_software_name(self):
        build_script = (PROJECT_ROOT / "build_installer.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("$AppName = -join ([char[]](0x5976, 0x9F99, 0x684C, 0x5BA0))", build_script)
        self.assertIn("--name $AppName", build_script)

    def test_installer_uses_chinese_software_name(self):
        installer_script = (PROJECT_ROOT / "packaging" / "nailong.iss").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn('#define MyAppName "奶龙桌宠"', installer_script)
        self.assertIn('#define MyAppExeName "奶龙桌宠.exe"', installer_script)
        self.assertIn(
            "OutputBaseFilename=奶龙桌宠-安装程序-{#MyAppVersion}-x64",
            installer_script,
        )
        self.assertIn('Source: "..\\build\\奶龙桌宠\\*"', installer_script)

    def test_installer_version_matches_application_version(self):
        installer_script = (PROJECT_ROOT / "packaging" / "nailong.iss").read_text(
            encoding="utf-8-sig"
        )
        match = re.search(r'#define MyAppVersion "([^"]+)"', installer_script)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), APP_VERSION)

    def test_build_finds_common_inno_setup_locations(self):
        build_script = (PROJECT_ROOT / "build_installer.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("${env:ProgramFiles(x86)}", build_script)
        self.assertIn("Test-Path -LiteralPath $Video", build_script)
        self.assertIn("Test-Path -LiteralPath $Icon", build_script)
        self.assertNotIn("--collect-all pygame", build_script)


if __name__ == "__main__":
    unittest.main()
