import unittest
from pathlib import Path

from configupdater import ConfigUpdater
from jinja2 import Template


REPOSITORY_ROOT = Path(__file__).parents[1]
USEFUL_MACROS = REPOSITORY_ROOT / "config" / "useful_macros.cfg"


class SafeSaveConfigTest(unittest.TestCase):
    def setUp(self):
        config = ConfigUpdater(
            strict=False,
            allow_no_value=True,
            space_around_delimiters=False,
            delimiters=(":", "="),
        )
        config.read(USEFUL_MACROS)
        section_name = "gcode_macro SAVE_CONFIG"
        self.assertTrue(
            config.has_section(section_name),
            "SAVE_CONFIG must be wrapped by useful_macros.cfg",
        )
        self.section = config[section_name]
        self.template = Template(self.section["gcode"].value)

    def render_commands(self, homed_axes, z):
        rendered = self.template.render(
            printer={
                "toolhead": {
                    "homed_axes": homed_axes,
                    "position": {"z": z},
                }
            }
        )
        return [line.strip() for line in rendered.splitlines() if line.strip()]

    def test_lifts_a_homed_z_axis_below_safe_height_before_saving(self):
        commands = self.render_commands("xyz", 2.5)

        self.assertEqual(
            commands,
            [
                "SAVE_GCODE_STATE NAME=_safe_save_config_state",
                "G90",
                "G0 Z10 F900",
                "RESTORE_GCODE_STATE NAME=_safe_save_config_state",
                "_SAVE_CONFIG",
            ],
        )

    def test_does_not_lower_a_homed_z_axis_already_above_safe_height(self):
        self.assertEqual(self.render_commands("xyz", 25.0), ["_SAVE_CONFIG"])

    def test_does_not_move_an_unhomed_z_axis(self):
        self.assertEqual(self.render_commands("xy", 0.0), ["_SAVE_CONFIG"])

    def test_delegates_to_the_original_save_config_command(self):
        self.assertEqual(self.section["rename_existing"].value, "_SAVE_CONFIG")


if __name__ == "__main__":
    unittest.main()
