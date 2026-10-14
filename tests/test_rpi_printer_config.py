import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from configupdater import ConfigUpdater


REPOSITORY_ROOT = Path(__file__).parents[1]


class RpiPrinterConfigTest(unittest.TestCase):
    def test_ender3_v3_se_generates_m4_screw_tilt_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            home = Path(temporary_directory)
            repository = home / "pellcorp"
            shutil.copytree(REPOSITORY_ROOT / "rpi", repository / "rpi")
            shutil.copytree(REPOSITORY_ROOT / "tools", repository / "tools")
            (home / "pellcorp-overrides").mkdir()

            shell = "sh" if os.name == "nt" else "bash"
            result = subprocess.run(
                [
                    shell,
                    (repository / "rpi" / "tools" / "apply-printer-cfg.sh").as_posix(),
                    "creality-ender3-v3-se",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            generated = home / "pellcorp-backups" / "printer.factory.cfg"
            self.assertTrue(generated.is_file())

            config = ConfigUpdater(
                strict=False,
                allow_no_value=True,
                space_around_delimiters=False,
                delimiters=(":", "="),
            )
            config.read(generated)
            self.assertTrue(config.has_section("screws_tilt_adjust"))
            section = config["screws_tilt_adjust"]
            self.assertEqual(section["screw1"].value, "54.5, 45.5")
            self.assertEqual(section["screw2"].value, "224.5, 45.5")
            self.assertEqual(section["screw3"].value, "224.5, 215.5")
            self.assertEqual(section["screw4"].value, "54.5, 215.5")
            self.assertEqual(section["screw_thread"].value, "CCW-M4")

    def test_ender3_v3_se_bltouch_enables_axis_twist_compensation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            home = Path(temporary_directory)
            repository = home / "pellcorp"
            shutil.copytree(REPOSITORY_ROOT / "rpi", repository / "rpi")
            shutil.copytree(REPOSITORY_ROOT / "tools", repository / "tools")
            (home / "pellcorp-overrides").mkdir()

            shell = "sh" if os.name == "nt" else "bash"
            result = subprocess.run(
                [
                    shell,
                    (repository / "rpi" / "tools" / "apply-printer-cfg.sh").as_posix(),
                    "creality-ender3-v3-se",
                ],
                env={**os.environ, "HOME": str(home)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            generated = home / "pellcorp-backups" / "bltouch.factory.cfg"
            self.assertTrue(generated.is_file())

            config = ConfigUpdater(
                strict=False,
                allow_no_value=True,
                space_around_delimiters=False,
                delimiters=(":", "="),
            )
            config.read(generated)
            self.assertTrue(config.has_section("axis_twist_compensation"))
            section = config["axis_twist_compensation"]
            self.assertEqual(section["calibrate_start_x"].value, "20")
            self.assertEqual(section["calibrate_end_x"].value, "200")
            self.assertEqual(section["calibrate_y"].value, "112.5")


if __name__ == "__main__":
    unittest.main()
