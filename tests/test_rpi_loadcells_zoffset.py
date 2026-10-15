import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[1]
INSTALLER = REPOSITORY_ROOT / "rpi" / "installer.sh"
KLIPPER_INSTALLER = REPOSITORY_ROOT / "rpi" / "install-klipper.sh"


class RpiLoadcellsZOffsetTest(unittest.TestCase):
    def extract_klipper_installer_function(self, name):
        installer = KLIPPER_INSTALLER.read_text()
        marker = f"function {name}()"
        self.assertIn(marker, installer, f"Klipper installer must define {name}")
        start = installer.index(marker)
        end = installer.find("\nfunction ", start + len(marker))
        self.assertNotEqual(end, -1, f"{name} must end before the next function")
        return installer[start:end]

    def extract_function(self, name):
        installer = INSTALLER.read_text()
        marker = f"function {name}()"
        self.assertIn(marker, installer, f"RPi installer must define {name}")
        start = installer.index(marker)
        end = installer.find("\nfunction ", start + len(marker))
        self.assertNotEqual(end, -1, f"{name} must end before the next function")
        return installer[start:end]

    def run_setup(self, done_contents="bltouch-probe\n"):
        setup_function = self.extract_function("setup_loadcells_zoffset")
        temporary_directory = tempfile.TemporaryDirectory()
        base = Path(temporary_directory.name)
        repository = base / "pellcorp"
        config_dir = base / "printer_data" / "config"
        patch_dir = repository / "k1" / "patches"
        overrides_dir = base / "pellcorp-overrides"
        for directory in (repository / "config", config_dir, patch_dir, overrides_dir):
            directory.mkdir(parents=True, exist_ok=True)

        shutil.copy(REPOSITORY_ROOT / "config" / "loadcells_zoffset.cfg", repository / "config")
        shutil.copy(REPOSITORY_ROOT / "config" / "loadcells_wipe.cfg", repository / "config")
        shutil.copy(
            REPOSITORY_ROOT / "k1" / "patches" / "loadcells_zoffset.cfg.e3v3se",
            patch_dir,
        )
        (base / "pellcorp.done").write_text(done_contents)

        calls = base / "config-helper.calls"
        helper = base / "config-helper"
        helper.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n')
        helper.chmod(0o755)

        runner = base / "runner.sh"
        runner.write_text(
            "#!/bin/bash\n"
            f"BASEDIR='{base.as_posix()}'\n"
            f"CONFIG_HELPER='{helper.as_posix()}'\n"
            "model=e3v3se\n"
            f"{setup_function}\n"
            "setup_loadcells_zoffset bltouch\n"
            "printf '%s' $? > \"$BASEDIR/status\"\n"
        )

        shell = "sh" if os.name == "nt" else "bash"
        result = subprocess.run(
            [shell, runner.as_posix()],
            env={**os.environ, "CALL_LOG": str(calls)},
            capture_output=True,
            text=True,
            check=False,
        )
        self.addCleanup(temporary_directory.cleanup)
        return base, calls, result

    def test_configures_e3v3se_loadcells_for_z_offset(self):
        base, calls, result = self.run_setup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((base / "status").read_text(), "1")
        self.assertTrue((base / "printer_data" / "config" / "loadcells_zoffset.cfg").is_file())
        self.assertTrue((base / "printer_data" / "config" / "loadcells_wipe.cfg").is_file())
        self.assertIn("loadcells-zoffset", (base / "pellcorp.done").read_text().splitlines())

        helper_calls = calls.read_text().splitlines()
        self.assertIn(
            "--file loadcells_zoffset.cfg --patches "
            f"{(base / 'pellcorp/k1/patches/loadcells_zoffset.cfg.e3v3se').as_posix()} --quiet",
            helper_calls,
        )
        self.assertIn('--add-include loadcells_zoffset.cfg', helper_calls)
        self.assertIn('--add-include loadcells_wipe.cfg', helper_calls)
        self.assertIn('--remove-include btteddy_zoffset.cfg', helper_calls)
        self.assertIn('--remove-section load_cell_probe', helper_calls)
        self.assertIn('--add-section load_cell_probe', helper_calls)
        self.assertIn(
            "--replace-section-entry load_cell_probe z_offset 0.0",
            helper_calls,
        )
        self.assertIn(
            "--file bltouch.cfg --replace-section-entry bed_mesh zero_reference_position 20,25",
            helper_calls,
        )

    def test_kalico_install_uses_secondary_probe_capable_rpi_fork(self):
        resolver = self.extract_klipper_installer_function(
            "klipper_repository_url"
        )
        runner = (
            "#!/bin/bash\n"
            f"{resolver}\n"
            "klipper_repository_url kalico\n"
            "klipper_repository_url klipper\n"
        )
        shell = "sh" if os.name == "nt" else "bash"
        result = subprocess.run(
            [shell],
            input=runner,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "https://github.com/kylemd/kalico-rpi.git",
                "https://github.com/pellcorp/klipper-rpi.git",
            ],
        )

    def test_existing_setup_is_unchanged(self):
        base, calls, result = self.run_setup("bltouch-probe\nloadcells-zoffset\n")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((base / "status").read_text(), "0")
        self.assertFalse(calls.exists())
        self.assertFalse((base / "printer_data" / "config" / "loadcells_zoffset.cfg").exists())

    def test_rejects_configuration_without_a_primary_probe(self):
        normalize_function = self.extract_function("normalize_model")
        validate_function = self.extract_function("validate_loadcells_zoffset")
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            patch_dir = base / "pellcorp" / "k1" / "patches"
            patch_dir.mkdir(parents=True)
            (patch_dir / "loadcells_zoffset.cfg.e3v3se").touch()
            runner = base / "runner.sh"
            runner.write_text(
                "#!/bin/bash\n"
                f"BASEDIR='{base.as_posix()}'\n"
                f"{normalize_function}\n"
                f"{validate_function}\n"
                "validate_loadcells_zoffset none e3v3se kalico\n"
            )

            shell = "sh" if os.name == "nt" else "bash"
            result = subprocess.run(
                [shell, runner.as_posix()],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("requires a primary probe", result.stdout)

    def test_rejects_unsupported_printer_and_non_kalico_fork(self):
        normalize_function = self.extract_function("normalize_model")
        validate_function = self.extract_function("validate_loadcells_zoffset")
        cases = (
            ("bltouch", "unsupported", "kalico", "not supported"),
            ("bltouch", "e3v3se", "klipper", "requires kalico"),
            ("loadcells", "e3v3se", "kalico", "not needed"),
        )
        for probe, model, klipper_fork, expected_message in cases:
            with self.subTest(probe=probe, model=model, klipper_fork=klipper_fork):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    base = Path(temporary_directory)
                    patch_dir = base / "pellcorp" / "k1" / "patches"
                    patch_dir.mkdir(parents=True)
                    (patch_dir / "loadcells_zoffset.cfg.e3v3se").touch()
                    runner = base / "runner.sh"
                    runner.write_text(
                        "#!/bin/bash\n"
                        f"BASEDIR='{base.as_posix()}'\n"
                        f"{normalize_function}\n"
                        f"{validate_function}\n"
                        f"validate_loadcells_zoffset {probe} {model} {klipper_fork}\n"
                    )

                    shell = "sh" if os.name == "nt" else "bash"
                    result = subprocess.run(
                        [shell, runner.as_posix()],
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                self.assertEqual(result.returncode, 1)
                self.assertIn(expected_message, result.stdout)

    def test_later_activation_backs_up_and_updates_managed_baseline(self):
        normalize_function = self.extract_function("normalize_model")
        validate_function = self.extract_function("validate_loadcells_zoffset")
        setup_function = self.extract_function("setup_loadcells_zoffset")
        activate_function = self.extract_function("activate_loadcells_zoffset")
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            repository = base / "pellcorp"
            config_dir = base / "printer_data" / "config"
            patch_dir = repository / "k1" / "patches"
            backups_dir = base / "pellcorp-backups"
            overrides_dir = base / "pellcorp-overrides"
            tools_dir = repository / "tools"
            for directory in (
                repository / "config",
                config_dir,
                patch_dir,
                backups_dir,
                overrides_dir,
                tools_dir,
            ):
                directory.mkdir(parents=True, exist_ok=True)

            shutil.copy(
                REPOSITORY_ROOT / "config" / "loadcells_zoffset.cfg",
                repository / "config",
            )
            shutil.copy(
                REPOSITORY_ROOT / "config" / "loadcells_wipe.cfg",
                repository / "config",
            )
            shutil.copy(
                REPOSITORY_ROOT / "k1" / "patches" / "loadcells_zoffset.cfg.e3v3se",
                patch_dir,
            )
            (base / "pellcorp.done").write_text("bltouch-probe\n")
            (config_dir / "printer.cfg").write_text("[printer]\nkinematics: cartesian\n")
            (config_dir / "bltouch.cfg").write_text("[bed_mesh]\n")

            events = base / "events"
            backup_script = tools_dir / "backups.sh"
            backup_script.write_text('#!/bin/bash\nprintf "backup %s\\n" "$*" >> "$EVENT_LOG"\n')
            backup_script.chmod(0o755)
            helper = base / "config-helper"
            helper.write_text('#!/bin/bash\nprintf "config %s\\n" "$*" >> "$EVENT_LOG"\n')
            helper.chmod(0o755)

            runner = base / "runner.sh"
            runner.write_text(
                "#!/bin/bash\n"
                f"BASEDIR='{base.as_posix()}'\n"
                f"CONFIG_HELPER='{helper.as_posix()}'\n"
                f"{normalize_function}\n"
                f"{validate_function}\n"
                f"{setup_function}\n"
                f"{activate_function}\n"
                "activate_loadcells_zoffset bltouch e3v3se kalico true\n"
                "printf '%s' $? > \"$BASEDIR/status\"\n"
            )

            shell = "sh" if os.name == "nt" else "bash"
            result = subprocess.run(
                [shell, runner.as_posix()],
                env={**os.environ, "EVENT_LOG": str(events)},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((base / "status").read_text(), "1")
            self.assertEqual(events.read_text().splitlines()[0], "backup --create")
            for filename in (
                "printer.cfg",
                "bltouch.cfg",
                "loadcells_zoffset.cfg",
                "loadcells_wipe.cfg",
            ):
                self.assertTrue((backups_dir / filename).is_file(), filename)

    def test_enabled_state_is_restored_from_install_marker(self):
        enabled_function = self.extract_function("loadcells_zoffset_is_enabled")
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            (base / "pellcorp.done").write_text(
                "mount=Default\nbltouch-probe\nloadcells-zoffset\ninstalled_sha=abc123\n"
            )
            runner = base / "runner.sh"
            runner.write_text(
                "#!/bin/bash\n"
                f"BASEDIR='{base.as_posix()}'\n"
                f"{enabled_function}\n"
                "loadcells_zoffset_is_enabled\n"
            )

            shell = "sh" if os.name == "nt" else "bash"
            result = subprocess.run(
                [shell, runner.as_posix()],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_model_normalization_removes_surrounding_whitespace(self):
        normalize_function = self.extract_function("normalize_model")
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            runner = base / "runner.sh"
            runner.write_text(
                "#!/bin/bash\n"
                f"{normalize_function}\n"
                "normalize_model '  k1  '\n"
            )

            shell = "sh" if os.name == "nt" else "bash"
            result = subprocess.run(
                [shell, runner.as_posix()],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "k1")


if __name__ == "__main__":
    unittest.main()
