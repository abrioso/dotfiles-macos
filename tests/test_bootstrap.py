"""Run bootstrap failure paths with isolated commands; never download or install."""
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bootstrap-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        (self.home / ".zshrc").write_text("existing shell configuration\n")
        self.tmp = self.base / "tmp"
        self.tmp.mkdir()
        self.actions = self.base / "actions"
        self.marker = self.base / "installer-ran"
        stub = '''import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["BOOTSTRAP_TEST_ACTIONS"], "a") as stream:
    stream.write(json.dumps([name] + args) + "\\n")
if name == "uname":
    print("Darwin" if args == ["-s"] else "arm64")
elif name == "id":
    print("501")
elif name == "sw_vers":
    print("15.0")
elif name == "sysctl":
    print("0")
elif name == "xcode-select":
    print("/test/CommandLineTools")
elif name == "curl":
    pathlib.Path(args[args.index("-o") + 1]).write_text(os.environ["BOOTSTRAP_TEST_INSTALLER"])
    sys.exit(22 if os.environ["BOOTSTRAP_TEST_MODE"] == "download" else 0)
elif name == "shasum":
    if os.environ["BOOTSTRAP_TEST_MODE"] == "hash-command":
        sys.exit(1)
    digest = "0" * 64 if os.environ["BOOTSTRAP_TEST_MODE"] == "checksum" else os.environ["BOOTSTRAP_TEST_DIGEST"]
    print(digest + "  " + args[-1])
else:
    sys.exit("Unexpected command")
'''
        for name in ("uname", "id", "sw_vers", "sysctl", "xcode-select", "curl", "shasum"):
            path = self.bin / name
            path.write_text("#!" + sys.executable + "\n" + stub)
            path.chmod(0o755)
        source = (ROOT / "setup-scripts/bootstrap.sh").read_text()
        # Redirect only fixed external tool paths and the install prefix in a copy.
        # The production download/checksum/execute control flow stays unchanged.
        for original in ("/usr/sbin/sysctl", "/usr/bin/xcode-select", "/usr/bin/curl", "/usr/bin/shasum"):
            self.assertIn(original, source)
            source = source.replace(original, shlex.quote(str(self.bin / Path(original).name)))
        source = source.replace("brew_prefix=/opt/homebrew", "brew_prefix=" + shlex.quote(str(self.base / "brew")))
        self.script = self.base / "bootstrap.sh"
        self.script.write_text(source)
        digest = next(line.split("=", 1)[1].strip() for line in source.splitlines()
                      if line.strip().startswith("installer_sha256="))
        installer = "#!/bin/bash\nprintf ran > " + shlex.quote(str(self.marker)) + "\nexit 37\n"
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                        HOME=str(self.home), TMPDIR=str(self.tmp),
                        BOOTSTRAP_TEST_ACTIONS=str(self.actions), BOOTSTRAP_TEST_DIGEST=digest,
                        BOOTSTRAP_TEST_INSTALLER=installer)

    def exercise(self, mode, expected, executed):
        before = {p.name: p.read_bytes() for p in self.home.iterdir()}
        run = subprocess.run(["/bin/bash", str(self.script), "--install-homebrew"],
                             env=dict(self.env, BOOTSTRAP_TEST_MODE=mode),
                             text=True, capture_output=True, timeout=15)
        self.assertEqual(run.returncode, expected, run.stdout + run.stderr)
        self.assertEqual(self.marker.exists(), executed)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.home.iterdir()})
        self.assertEqual(list(self.tmp.iterdir()), [])
        self.assertFalse((self.base / "brew").exists())
        actions = [json.loads(line)[0] for line in self.actions.read_text().splitlines()]
        self.assertIn("curl", actions)
        self.assertEqual("shasum" in actions, mode != "download")
        return run

    def test_failed_download_never_executes_partial_installer(self):
        self.exercise("download", 22, False)

    def test_checksum_mismatch_never_executes_installer(self):
        run = self.exercise("checksum", 2, False)
        self.assertIn("checksum mismatch", run.stderr)

    def test_checksum_command_failure_never_executes_installer(self):
        self.exercise("hash-command", 1, False)

    def test_verified_installer_failure_stops_and_cleans_up(self):
        self.exercise("installer", 37, True)
