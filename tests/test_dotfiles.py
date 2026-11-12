"""Regression coverage for safety boundaries, preserved state and command failures."""
import copy
import errno
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import pty
import plistlib
import platform
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "setup-scripts"))
from lib.config import ConfigError, brewfile, load_for_configure, read_json, validate
from lib.deployment import BEGIN, END, Deployment, atomic_write, marked_text
from lib.modules import desired_files, git_text
from lib.system import installed_packages, preference_state, require_mac
from lib.tui import toggle

spec = importlib.util.spec_from_file_location("dotfiles_cli", ROOT / "setup-scripts/dotfiles.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def result(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dotfiles-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        # These tests always start from the tracked template, not machine selections.
        self.config = read_json(ROOT / "dotfiles-configurations/config.json.example")
        self.catalog = read_json(ROOT / "dotfiles-configurations/packages.json.example")
        self.environment = patch.dict(os.environ, {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.home / ".config")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for key in ("ZDOTDIR", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_COUNT"):
            if key in os.environ:
                self.environment_old = os.environ.pop(key)
                self.addCleanup(os.environ.__setitem__, key, self.environment_old)


class ConfigurationTests(Sandbox):
    def test_templates_and_package_order(self):
        validate(self.config, self.catalog)
        text = brewfile(self.config, self.catalog)
        self.assertEqual(text.count('brew "git"'), 1)
        self.assertNotIn("docker", text)
        self.assertNotIn("microsoft-office", text)

    def test_empty_selection_is_real_opt_out(self):
        self.config.update(package_groups=[], modules=[])
        validate(self.config, self.catalog)
        self.assertEqual(brewfile(self.config, self.catalog), "")
        self.assertEqual(desired_files(ROOT, self.home, self.config), {})

    def test_reject_invalid_configuration_before_apply(self):
        variants = [
            {"schema_version": True}, {"schema_version": 2}, {"unknown": 1},
            {"modules": ["../other"]}, {"modules": ["shell", "shell"]},
            {"package_groups": "base"}, {"package_groups": ["missing"]},
            {"package_groups": ["colima", "docker-desktop"]},
            {"modules": ["pwsh"], "package_groups": []},
            {"git": {"core.hooksPath": "/tmp/hook"}},
            {"git": {"alias.st": "!evil"}}, {"git": {"user.name": "one\ntwo"}},
            {"macos": {"show_file_extensions": "true"}},
        ]
        for update in variants:
            with self.subTest(update=update):
                candidate = copy.deepcopy(self.config)
                candidate.update(update)
                with self.assertRaises(ConfigError):
                    validate(candidate, self.catalog)

    def test_catalog_cannot_inject_brewfile_ruby(self):
        self.catalog["base"]["formulae"] = ['git"; system("bad")']
        with self.assertRaises(ConfigError):
            validate(self.config, self.catalog)

    def test_duplicate_json_keys_are_rejected(self):
        path = self.base / "bad.json"
        path.write_text('{"modules": [], "modules": ["shell"]}')
        with self.assertRaises(ConfigError):
            read_json(path)

    def test_switching_container_toggle_excludes_previous_runtime(self):
        self.config["package_groups"] = ["colima"]
        toggle(self.config, "package_groups", "docker-desktop")
        self.assertEqual(self.config["package_groups"], ["docker-desktop"])
        toggle(self.config, "package_groups", "docker-desktop")
        self.assertEqual(self.config["package_groups"], [])


class DeploymentTests(Sandbox):
    def test_idempotency_and_backups_preserve_user_content(self):
        target = self.home / ".zshrc"
        target.write_text("# existing custom settings\nexport EXAMPLE=kept\n")
        self.config["modules"] = ["shell"]
        first = Deployment(self.home)
        for path, text in desired_files(ROOT, self.home, self.config).items():
            first.write(path, text)
        self.assertIn("export EXAMPLE=kept", target.read_text())
        entries = json.loads((first.backup_dir / "manifest.json").read_text())
        entry = next(x for x in entries if x["path"] == str(target))
        self.assertEqual((first.backup_dir / entry["backup"]).read_text(), "# existing custom settings\nexport EXAMPLE=kept\n")
        before = target.stat().st_mtime_ns
        second = Deployment(self.home)
        for path, text in desired_files(ROOT, self.home, self.config).items():
            self.assertFalse(second.write(path, text))
        self.assertEqual(before, target.stat().st_mtime_ns)
        self.assertIsNone(second.backup_dir)

    def test_deployed_files_are_independent_copies(self):
        path = self.home / "theme"
        source = self.base / "source"
        source.write_text("theme A")
        Deployment(self.home).write(path, source.read_text())
        source.write_text("theme B")
        self.assertEqual(path.read_text(), "theme A")

    def test_symlink_file_and_parent_refused(self):
        source = self.base / "source"
        source.write_text("original")
        link = self.home / ".zshrc"
        link.symlink_to(source)
        with self.assertRaises(ConfigError):
            Deployment(self.home).write(link, "overwrite")
        self.assertEqual(source.read_text(), "original")
        directory = self.home / "linked"
        directory.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(ConfigError):
            atomic_write(directory / "new", b"bad")
        self.assertFalse((self.base / "new").exists())

    def test_hardlink_is_detached_without_changing_original(self):
        original = self.base / "original"
        target = self.home / "target"
        original.write_text("same")
        os.link(original, target)
        self.assertTrue(Deployment(self.home).write(target, "same"))
        self.assertEqual(target.stat().st_nlink, 1)
        target.write_text("new")
        self.assertEqual(original.read_text(), "same")

    def test_failed_atomic_publication_preserves_original_and_backup(self):
        target = self.home / "target"
        target.write_text("old")
        deployment = Deployment(self.home)
        real_replace = os.replace

        def fail_target(source, destination):
            if Path(destination) == target:
                raise OSError("simulated write failure")
            return real_replace(source, destination)

        with patch("lib.deployment.os.replace", side_effect=fail_target):
            with self.assertRaises(OSError):
                deployment.write(target, "new")
        self.assertEqual(target.read_text(), "old")
        self.assertEqual((deployment.backup_dir / "0.bak").read_text(), "old")
        self.assertFalse(list(self.home.glob(".dotfiles-*")))

    def test_marker_conflicts_fail_closed(self):
        for old in ("# >>> dotfiles-macos >>>\n", "# <<< dotfiles-macos <<<\n",
                    "prefix# >>> dotfiles-macos >>>\n# <<< dotfiles-macos <<<\n",
                    "# <<< dotfiles-macos <<<\n# >>> dotfiles-macos >>>\n"):
            with self.subTest(old=old), self.assertRaises(ConfigError):
                marked_text(old, "content")

    def test_adjacent_marker_text_preserves_profile_and_prevents_install(self):
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        target = self.home / ".zshrc"
        for old in (
            BEGIN + "export KEEP=1\nmanaged\n" + END + "\n",
            BEGIN + "\nmanaged\nexport KEEP=1" + END + "\n",
            "export KEEP=1" + BEGIN + "\nmanaged\n" + END + "\n",
            BEGIN + "\nmanaged\n" + END + "export KEEP=1\n",
            BEGIN + " \nmanaged\n" + END + "\n",
            BEGIN + "\nmanaged\n " + END + "\n",
        ):
            with self.subTest(old=old):
                target.write_text(old)
                with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
                     patch.object(cli, "require_mac"), patch.object(cli, "homebrew") as brew:
                    with self.assertRaises(ConfigError):
                        cli.setup(args)
                    brew.assert_not_called()
                self.assertEqual(target.read_text(), old)
                self.assertEqual(list(self.home.iterdir()), [target])

    def test_complete_marker_lines_preserve_surrounding_content_and_eof(self):
        prefix = "export KEEP_BEFORE=1\n"
        for suffix in ("", "\n", "\nexport KEEP_AFTER=1\n"):
            old = prefix + BEGIN + "\nold content\n" + END + suffix
            expected = prefix + BEGIN + "\nnew content\n" + END + suffix
            with self.subTest(suffix=suffix):
                self.assertEqual(marked_text(old, "new content"), expected)
                self.assertEqual(marked_text(expected, "new content"), expected)

    def test_git_escaping_round_trips_and_preserves_existing_settings(self):
        self.config["modules"] = ["git"]
        name = 'André "quoted" \\ value'
        self.config["git"]["user.name"] = name
        target = self.home / ".gitconfig"
        target.write_text("[custom]\n\tkeep = true\n")
        for path, text in desired_files(ROOT, self.home, self.config).items():
            Deployment(self.home).write(path, text)
        query = subprocess.run(["git", "config", "--global", "--includes", "--get", "user.name"], capture_output=True, text=True)
        self.assertEqual(query.returncode, 0)
        self.assertEqual(query.stdout.rstrip("\n"), name)
        query = subprocess.run(["git", "config", "--global", "--includes", "--get", "custom.keep"], capture_output=True, text=True)
        self.assertEqual(query.stdout.strip(), "true")

    def test_existing_xdg_git_config_is_not_shadowed(self):
        target = self.home / ".config/git/config"
        target.parent.mkdir(parents=True)
        target.write_text("[user]\n\tname = Existing\n")
        self.config["modules"] = ["git"]
        with self.assertRaises(ConfigError):
            desired_files(ROOT, self.home, self.config)
        self.assertFalse((self.home / ".gitconfig").exists())

    def test_empty_identity_not_written_and_windows_defaults_not_copied(self):
        text = git_text(self.config["git"])
        self.assertNotIn("[user]", text)
        self.assertNotIn("ignorecase", text)
        self.assertNotIn("filemode", text)


class CommandTests(Sandbox):
    def test_apply_and_diagnostic_converge_without_packages(self):
        self.config["git"].update({"user.name": "Test", "user.email": "test@example.invalid"})
        self.config["package_groups"] = []
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        diagnostic = type("Args", (), {"json": True, "check_packages": False})()
        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli.platform, "system", return_value="Darwin"), \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(cli.setup(args), 0)
            before = (self.home / ".zshrc").stat().st_mtime_ns
            self.assertEqual(cli.setup(args), 0)
            self.assertEqual(before, (self.home / ".zshrc").stat().st_mtime_ns)
            self.assertEqual(cli.verify(diagnostic), 0)
            theme = self.home / ".config/dotfiles-macos/theme.omp.json"
            theme.write_text("modified")
            self.assertEqual(cli.verify(diagnostic), 1)

    def test_package_query_failure_is_not_missing(self):
        with patch("lib.system.run", return_value=result(2)):
            with self.assertRaises(ConfigError):
                installed_packages("brew")

    def test_native_mac_preflight_refuses_rosetta_and_root(self):
        with patch("lib.system.platform.system", return_value="Darwin"), \
             patch("lib.system.platform.mac_ver", return_value=("15.8", (), "")), \
             patch("lib.system.os.geteuid", return_value=501), \
             patch("lib.system.run", return_value=result(stdout="1\n")):
            with self.assertRaisesRegex(ConfigError, "Rosetta"):
                require_mac()
        with patch("lib.system.platform.system", return_value="Darwin"), \
             patch("lib.system.os.geteuid", return_value=0):
            with self.assertRaisesRegex(ConfigError, "sudo"):
                require_mac()

    def test_identity_uses_existing_global_values_without_prompting(self):
        self.config["git"]["user.name"] = "Local Name"
        with patch.object(cli, "run", return_value=result(stdout="global@example.invalid\n")) as query, \
             patch("builtins.input") as prompt:
            completed = cli.complete_git_identity(self.config, self.catalog, True)
        self.assertEqual(completed["git"]["user.name"], "Local Name")
        self.assertEqual(completed["git"]["user.email"], "global@example.invalid")
        self.assertEqual(self.config["git"]["user.email"], "")
        query.assert_called_once_with(["git", "config", "--global", "--includes", "--get", "user.email"])
        prompt.assert_not_called()

    def test_identity_missing_noninteractive_and_cancel_leave_state_unchanged(self):
        original = copy.deepcopy(self.config)
        for interactive, failure in ((False, ConfigError), (True, EOFError), (True, KeyboardInterrupt)):
            with self.subTest(interactive=interactive, failure=failure), \
                 patch.object(cli, "run", return_value=result(1)), \
                 patch("builtins.input", side_effect=failure):
                with self.assertRaises(ConfigError if failure is EOFError else failure):
                    cli.complete_git_identity(self.config, self.catalog, interactive)
            self.assertEqual(self.config, original)
            self.assertEqual(list(self.home.iterdir()), [])

    def test_identity_disabled_module_never_queries_or_prompts(self):
        self.config["modules"] = []
        with patch.object(cli, "run") as query, patch("builtins.input") as prompt:
            self.assertEqual(cli.complete_git_identity(self.config, self.catalog, True), self.config)
        query.assert_not_called()
        prompt.assert_not_called()

    def test_identity_prompt_saves_json_and_applies_global_git(self):
        checkout = self.base / "identity-checkout"
        directory = checkout / "dotfiles-configurations"
        directory.mkdir(parents=True)
        local = directory / "config.json"
        self.config.update(package_groups=[], modules=["git"])
        local.write_text(json.dumps(self.config))
        args = type("Args", (), {"plan": False, "json": False, "yes": False})()
        with patch.object(cli, "ROOT", checkout), \
             patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli, "run", return_value=result(1)), \
             patch("sys.stdin.isatty", return_value=True), \
             patch("builtins.input", side_effect=["y", "", "André Test", "test@example.invalid"]), \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(cli.setup(args), 0)
        saved = json.loads(local.read_text())
        for key, expected in (("user.name", "André Test"), ("user.email", "test@example.invalid")):
            self.assertEqual(saved["git"][key], expected)
            query = subprocess.run(["git", "config", "--global", "--includes", "--get", key],
                                   text=True, capture_output=True)
            self.assertEqual(query.returncode, 0, query.stderr)
            self.assertEqual(query.stdout.strip(), expected)
        self.assertEqual(saved["package_groups"], [])
        self.assertTrue(list(self.home.rglob("manifest.json")))

    def test_defaults_reads_typed_preferences_and_missing_keys(self):
        for data, expected in (({}, {"exists": False}),
                               ({"key": True}, {"exists": True, "value": True}),
                               ({"key": False}, {"exists": True, "value": False})):
            with self.subTest(data=data), patch("lib.system.run", return_value=result(
                    stdout=plistlib.dumps(data).decode())) as command:
                self.assertEqual(preference_state("domain", "key"), expected)
                command.assert_called_once_with(["/usr/bin/defaults", "export", "domain", "-"])

    def test_defaults_rejects_errors_invalid_plists_and_non_booleans(self):
        for response in (result(1, stderr="Permission denied"), result(1, stdout="Usage: defaults"),
                         result(stdout="not a plist"),
                         result(stdout=plistlib.dumps([]).decode()),
                         *(result(stdout=plistlib.dumps({"key": value}).decode())
                           for value in (0, 1, "true", "false"))):
            with self.subTest(response=response), patch("lib.system.run", return_value=response):
                with self.assertRaisesRegex(ConfigError, "domain/key"):
                    preference_state("domain", "key")

    @unittest.skipUnless(platform.system() == "Darwin", "Requires macOS defaults")
    def test_native_defaults_reads_temporary_plist_without_changing_preferences(self):
        # Absolute plist domains exercise the real utility without writing user defaults.
        domain = self.base / "preferences.plist"
        for data, expected in (({}, {"exists": False}),
                               ({"key": True}, {"exists": True, "value": True}),
                               ({"key": False}, {"exists": True, "value": False})):
            with self.subTest(data=data):
                domain.write_bytes(plistlib.dumps(data))
                before = domain.read_bytes()
                self.assertEqual(preference_state(str(domain), "key"), expected)
                self.assertEqual(domain.read_bytes(), before)

    def test_preference_read_failure_prevents_install_and_deployment(self):
        self.config["modules"] = ["macos"]
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli, "homebrew") as brew, \
             patch("lib.system.run", return_value=result(1, stderr="Permission denied")):
            with self.assertRaisesRegex(ConfigError, "Permission denied"):
                cli.setup(args)
            brew.assert_not_called()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_backup_conflicts_prevent_package_installation(self):
        self.config["git"].update({"user.name": "Test", "user.email": "test@example.invalid"})
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        for name in (".local", ".local/state", ".local/state/dotfiles-macos/backups"):
            for kind in ("symlink", "file"):
                with self.subTest(name=name, kind=kind):
                    path = self.home / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if kind == "symlink":
                        path.symlink_to(self.base / "absent")
                    else:
                        path.write_text("preserve")
                    try:
                        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
                             patch.object(cli, "require_mac"), patch.object(cli, "homebrew") as brew:
                            with self.assertRaisesRegex(ConfigError, "backup|Backup"):
                                cli.setup(args)
                            brew.assert_not_called()
                        self.assertFalse((self.home / ".zshrc").exists())
                        if kind == "file":
                            self.assertEqual(path.read_text(), "preserve")
                    finally:
                        shutil.rmtree(self.home / ".local") if (self.home / ".local").is_dir() else (self.home / ".local").unlink()

    def test_profile_edits_during_install_are_preserved(self):
        self.config["modules"] = ["shell", "git", "pwsh"]
        self.config["package_groups"] = ["pwsh"]
        self.config["git"].update({"user.name": "Test", "user.email": "test@example.invalid"})
        profiles = {self.home / ".zshrc": "export KEEP_ZSHRC=1\n",
                    self.home / ".zprofile": "export KEEP_ZPROFILE=1\n",
                    self.home / ".gitconfig": "[custom]\n    keep = yes\n",
                    self.home / ".config/powershell/profile.ps1": "$KeepProfile = 1\n"}
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        real_run = subprocess.run

        def installer(command, **kwargs):
            if command[0] != "test-brew":
                return real_run(command, **kwargs)
            for path, content in profiles.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            return result()

        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli, "homebrew", return_value="test-brew"), \
             patch.object(cli, "installed_packages", return_value=cli.packages(self.config, self.catalog)), \
             patch.object(cli.subprocess, "run", side_effect=installer), \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(cli.setup(args), 0)
        for path, content in profiles.items():
            self.assertIn(content, path.read_text())
            self.assertIn(BEGIN, path.read_text())

    def test_profile_conflict_during_install_aborts_before_deployment(self):
        self.config["modules"] = ["shell"]
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        profile = self.home / ".zshrc"
        conflict = BEGIN + " invalid marker\n"

        def installer(*args, **kwargs):
            profile.write_text(conflict)
            return result()

        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli, "homebrew", return_value="test-brew"), \
             patch.object(cli, "installed_packages", return_value=cli.packages(self.config, self.catalog)), \
             patch.object(cli.subprocess, "run", side_effect=installer):
            with self.assertRaises(ConfigError):
                cli.setup(args)
        self.assertEqual(profile.read_text(), conflict)
        self.assertEqual(list(self.home.iterdir()), [profile])

    def test_preferences_changed_during_install_converge_with_fresh_backup(self):
        from lib.config import PREFERENCES
        self.config["modules"] = ["macos"]
        states = {PREFERENCES[name]: {"exists": True, "value": desired}
                  for name, desired in self.config["macos"].items()}
        changed = next(iter(PREFERENCES))
        domain, key = PREFERENCES[changed]
        desired = self.config["macos"][changed]
        writes = []
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()

        def installer(*args, **kwargs):
            states[(domain, key)] = {"exists": True, "value": not desired}
            return result()

        def write_preference(command):
            backups = list(self.home.rglob("macos-preferences.json"))
            self.assertEqual(len(backups), 1)
            saved = json.loads(backups[0].read_text())
            self.assertEqual(saved[0]["previous"], {"exists": True, "value": not desired})
            writes.append(command)
            states[(command[2], command[3])] = {"exists": True, "value": command[-1] == "true"}
            return result()

        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli, "homebrew", return_value="test-brew"), \
             patch.object(cli, "installed_packages", return_value=cli.packages(self.config, self.catalog)), \
             patch.object(cli.subprocess, "run", side_effect=installer), \
             patch("lib.modules.preference_state", side_effect=lambda d, k: dict(states[(d, k)])), \
             patch("lib.modules.run", side_effect=write_preference), \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(cli.setup(args), 0)
        self.assertEqual(len(writes), 1)
        for name, value in self.config["macos"].items():
            self.assertEqual(states[PREFERENCES[name]], {"exists": True, "value": value})

    def test_preference_recheck_failure_prevents_managed_writes(self):
        self.config["modules"] = ["shell", "macos"]
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli, "homebrew", return_value="test-brew"), \
             patch.object(cli, "installed_packages", return_value=cli.packages(self.config, self.catalog)), \
             patch.object(cli.subprocess, "run", return_value=result()), \
             patch.object(cli, "prepare_preferences", side_effect=[[], ConfigError("Preference changed type")]), \
             patch.object(cli, "apply_preferences") as apply:
            with self.assertRaisesRegex(ConfigError, "changed type"):
                cli.setup(args)
            apply.assert_not_called()
        self.assertEqual(list(self.home.iterdir()), [])

    def test_failed_package_install_never_changes_dotfiles(self):
        self.config["git"].update({"user.name": "Test", "user.email": "test@example.invalid"})
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli, "homebrew", return_value="brew"), \
             patch.object(cli.subprocess, "run", return_value=result(1)):
            with self.assertRaisesRegex(ConfigError, "Package installation failed"):
                cli.setup(args)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_preflight_conflict_precedes_install(self):
        (self.home / ".zshrc").symlink_to(self.base / "missing")
        args = type("Args", (), {"plan": False, "json": False, "yes": True})()
        with patch.object(cli, "load", return_value=(self.config, self.catalog)), \
             patch.object(cli, "require_mac"), patch.object(cli, "homebrew") as brew:
            with self.assertRaises(ConfigError):
                cli.setup(args)
            brew.assert_not_called()

    def test_preference_backup_precedes_mutation(self):
        from lib.modules import apply_preferences
        deployment = Deployment(self.home)
        pending = [{"name": "show_path_bar", "domain": "com.apple.finder", "key": "ShowPathbar",
                    "previous": {"exists": False}, "desired": True}]

        def fail_after_backup(args):
            self.assertEqual(json.loads((deployment.backup_dir / "macos-preferences.json").read_text()), pending)
            return result(1)

        with patch("lib.modules.run", side_effect=fail_after_backup):
            with self.assertRaises(ConfigError):
                apply_preferences(pending, deployment)


class CLITests(Sandbox):
    def setUp(self):
        super().setUp()
        self.checkout = self.base / "checkout"
        shutil.copytree(ROOT, self.checkout, ignore=shutil.ignore_patterns(".git", "__pycache__", "config.json", "packages.json"))

    def invoke(self, *args):
        return subprocess.run([sys.executable, "-B", str(self.checkout / "setup-scripts/dotfiles.py"), *args],
                              env=os.environ.copy(), text=True, capture_output=True)

    def snapshot(self):
        return {str(p.relative_to(self.base)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.base.rglob("*") if p.is_file()}

    def test_unsafe_configuration_paths_fail_before_reading(self):
        directory = self.checkout / "dotfiles-configurations"
        regular = self.base / "target.json"
        regular.write_text('{"preserve": true}')
        fifo = self.base / "pipe"
        os.mkfifo(fifo)
        for name in ("config.json", "packages.json"):
            for kind, target in (("regular-link", regular), ("fifo-link", fifo),
                                 ("dangling-link", self.base / "absent"), ("fifo", None)):
                with self.subTest(name=name, kind=kind):
                    path = directory / name
                    if target is None:
                        os.mkfifo(path)
                    else:
                        path.symlink_to(target)
                    try:
                        for args in (("configure", "--defaults"), ("setup", "--plan"), ("verify",)):
                            output = subprocess.run(
                                [sys.executable, "-B", str(self.checkout / "setup-scripts/dotfiles.py"), *args],
                                env=os.environ.copy(), text=True, capture_output=True, timeout=5)
                            self.assertEqual(output.returncode, 2, output.stderr)
                            self.assertRegex(output.stderr, "Symlink destination|not a regular file")
                        self.assertEqual(regular.read_text(), '{"preserve": true}')
                        self.assertEqual(list(self.home.iterdir()), [])
                    finally:
                        path.unlink()

    def test_missing_config_plan_is_read_only(self):
        before = self.snapshot()
        output = self.invoke("setup", "--plan")
        self.assertEqual(output.returncode, 2)
        self.assertEqual(before, self.snapshot())

    def test_plan_and_verify_do_not_write_or_disclose_identity(self):
        self.assertEqual(self.invoke("configure", "--defaults").returncode, 0)
        path = self.checkout / "dotfiles-configurations/config.json"
        data = json.loads(path.read_text())
        data["git"]["user.email"] = "private-marker@example.invalid"
        path.write_text(json.dumps(data))
        before = self.snapshot()
        plan = self.invoke("setup", "--plan", "--json", "--verbose")
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(json.loads(plan.stdout)["personal_values"], "omitted")
        self.assertIn("[verbose]", plan.stderr)
        check = self.invoke("verify", "--json")
        self.assertEqual(check.returncode, 1)
        self.assertNotIn("private-marker", plan.stdout + plan.stderr + check.stdout + check.stderr)
        self.assertEqual(before, self.snapshot())

    def test_configure_defaults_preserves_opt_out(self):
        self.invoke("configure", "--defaults")
        path = self.checkout / "dotfiles-configurations/config.json"
        data = json.loads(path.read_text())
        data.update(package_groups=[], modules=[])
        path.write_text(json.dumps(data))
        self.assertEqual(self.invoke("configure", "--defaults").returncode, 0)
        saved = json.loads(path.read_text())
        self.assertEqual(saved["package_groups"], [])
        self.assertEqual(saved["modules"], [])

    def test_non_interactive_tui_refuses_without_creating_files(self):
        before = self.snapshot()
        output = self.invoke("configure")
        self.assertEqual(output.returncode, 2)
        self.assertEqual(before, self.snapshot())

    def test_tui_cancel_and_toggle_save_in_real_terminal(self):
        def terminal(keys):
            master, slave = pty.openpty()
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 120, 0, 0))
            env = dict(os.environ, TERM="xterm-256color")
            process = subprocess.Popen([sys.executable, "-B", str(self.checkout / "setup-scripts/dotfiles.py"), "configure"],
                                       stdin=slave, stdout=slave, stderr=slave, env=env)
            os.close(slave)
            output = b""
            try:
                deadline = time.monotonic() + 8
                while b"dotfiles-macos |" not in output and time.monotonic() < deadline:
                    if select.select([master], [], [], 0.2)[0]:
                        output += os.read(master, 65536)
                self.assertIn(b"dotfiles-macos |", output)
                os.write(master, keys)
                # Keep draining output while curses redraws and restores the terminal.
                # Waiting without reading can fill the smaller macOS PTY buffer.
                deadline = time.monotonic() + 5
                while process.poll() is None and time.monotonic() < deadline:
                    if select.select([master], [], [], 0.1)[0]:
                        try:
                            chunk = os.read(master, 65536)
                        except OSError as exc:
                            if exc.errno != errno.EIO:
                                raise
                            break  # Linux reports EIO when the slave closes.
                        if not chunk:
                            break  # macOS reports EOF instead.
                        output += chunk
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
                self.assertEqual(process.returncode, 0, output.decode(errors="replace"))
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)

        before = self.snapshot()
        terminal(b" q")  # Toggle base, then cancel: no local configuration is written.
        self.assertEqual(before, self.snapshot())
        terminal(b" s")  # Toggle base off, then save.
        saved = json.loads((self.checkout / "dotfiles-configurations/config.json").read_text())
        self.assertNotIn("base", saved["package_groups"])
        self.assertIn("terminal", saved["package_groups"])

    def git(self, directory, *arguments):
        value = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True, text=True)
        self.assertEqual(value.returncode, 0, value.stderr)
        return value.stdout.strip()

    def update_repositories(self):
        git = self.git
        remote = self.base / "origin.git"
        remote.mkdir()
        git(remote, "init", "--bare")
        git(self.checkout, "init", "-b", "feature/test")
        git(self.checkout, "config", "user.name", "Test")
        git(self.checkout, "config", "user.email", "test@example.invalid")
        git(self.checkout, "add", ".")
        git(self.checkout, "commit", "-m", "seed")
        git(self.checkout, "remote", "add", "origin", str(remote))
        git(self.checkout, "push", "-u", "origin", "feature/test")
        self.invoke("configure", "--defaults")
        local = self.checkout / "dotfiles-configurations/config.json"
        local_bytes = local.read_bytes()
        writer = self.base / "writer"
        git(self.base, "clone", "--branch", "feature/test", str(remote), str(writer))
        git(writer, "config", "user.name", "Test")
        git(writer, "config", "user.email", "test@example.invalid")
        return writer, local, local_bytes

    def test_update_fast_forwards_preserves_json_and_refuses_divergence(self):
        git = self.git
        writer, local, local_bytes = self.update_repositories()
        (writer / "new.txt").write_text("one")
        git(writer, "add", "new.txt")
        git(writer, "commit", "-m", "new upstream")
        git(writer, "push")
        output = self.invoke("update")
        self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual((self.checkout / "new.txt").read_text(), "one")
        self.assertEqual(local.read_bytes(), local_bytes)
        self.assertFalse((self.home / ".zshrc").exists())
        (self.checkout / "local.txt").write_text("local")
        git(self.checkout, "add", "local.txt")
        git(self.checkout, "commit", "-m", "local divergence")
        before = git(self.checkout, "rev-parse", "HEAD")
        (writer / "new.txt").write_text("two")
        git(writer, "commit", "-am", "remote divergence")
        git(writer, "push")
        output = self.invoke("update")
        self.assertEqual(output.returncode, 2)
        self.assertEqual(git(self.checkout, "rev-parse", "HEAD"), before)
        self.assertEqual(local.read_bytes(), local_bytes)

    def test_update_refuses_upstream_local_configuration_paths(self):
        writer, _, _ = self.update_repositories()
        before = self.git(self.checkout, "rev-parse", "HEAD")
        local_paths = [self.checkout / "dotfiles-configurations" / name
                       for name in ("config.json", "packages.json")]
        contents = {path: path.read_bytes() for path in local_paths}
        for name in ("config.json", "packages.json"):
            with self.subTest(path=name):
                self.git(writer, "reset", "--hard", before)
                path = writer / "dotfiles-configurations" / name
                path.write_text('{"upstream": true}\n')
                self.git(writer, "add", "--force", str(path))
                self.git(writer, "commit", "-m", "track reserved configuration")
                self.git(writer, "push", "--force")
                output = self.invoke("update")
                self.assertEqual(output.returncode, 2, output.stderr)
                self.assertIn("reserved local configuration", output.stderr)
                self.assertEqual(self.git(self.checkout, "rev-parse", "HEAD"), before)
                for local, data in contents.items():
                    self.assertEqual(local.read_bytes(), data)
                self.assertFalse((self.home / ".zshrc").exists())

    def test_non_macos_apply_refused(self):
        with patch.object(cli.platform, "system", return_value="Linux"):
            with self.assertRaises(ConfigError):
                require_mac()

    def test_gitflow_hook_matches_full_remote_refs(self):
        hook = ROOT / "git-hooks/pre-push"
        for remote, expected in (("refs/heads/main", 1), ("refs/heads/develop", 1),
                                 ("refs/heads/feature/main", 0), ("refs/tags/main", 0)):
            with self.subTest(remote=remote):
                output = subprocess.run(["sh", str(hook)], input="local sha " + remote + " sha\n", text=True, capture_output=True)
                self.assertEqual(output.returncode, expected)


if __name__ == "__main__":
    unittest.main()
