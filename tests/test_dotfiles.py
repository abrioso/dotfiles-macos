"""Regression coverage for safety boundaries, preserved state and command failures."""
import copy
import fcntl
import hashlib
import importlib.util
import io
import json
import os
import pty
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
from lib.deployment import Deployment, atomic_write, marked_text
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

    def test_defaults_distinguishes_missing_and_failure(self):
        with patch("lib.system.run", return_value=result(1, stderr="The domain/default pair does not exist")):
            self.assertEqual(preference_state("domain", "key"), {"exists": False})
        with patch("lib.system.run", return_value=result(1, stderr="unexpected failure")):
            with self.assertRaises(ConfigError):
                preference_state("domain", "key")

    def test_failed_package_install_never_changes_dotfiles(self):
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
        plan = self.invoke("setup", "--plan", "--json")
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(json.loads(plan.stdout)["personal_values"], "omitted")
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
                process.wait(timeout=5)
                self.assertEqual(process.returncode, 0)
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

    def test_update_fast_forwards_preserves_json_and_refuses_divergence(self):
        def git(directory, *arguments):
            value = subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True, text=True)
            self.assertEqual(value.returncode, 0, value.stderr)
            return value.stdout.strip()

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
