"""Exercise the publication script without GitHub access or real pushes."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="publication-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.checkout = self.base / "checkout"
        shutil.copytree(ROOT, self.checkout, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "config.json", "packages.json"))
        self.real_git = shutil.which("git")
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("add", "README.md")
        self.git("commit", "-m", "seed")
        self.seed = self.git("rev-parse", "HEAD")
        self.git("branch", "develop")
        self.git("switch", "-c", "feature/initial-macos")
        self.git("add", ".")
        self.git("commit", "-m", "implementation")
        self.previous = self.git("rev-parse", "HEAD")
        self.git("commit", "--allow-empty", "-m", "follow-up")
        self.head = self.git("rev-parse", "HEAD")
        self.git("remote", "add", "origin", "https://github.com/abrioso/dotfiles-macos.git")
        self.refs = self.base / "remote-refs"
        self.actions = self.base / "actions"
        self.actions.write_text("")
        binaries = self.base / "bin"
        binaries.mkdir()
        stub = '''import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
name = pathlib.Path(sys.argv[0]).name
def record():
    with open(os.environ["PUBLICATION_TEST_ACTIONS"], "a") as stream:
        stream.write(json.dumps([name] + args) + "\\n")
if name == "gh":
    if args[:2] == ["api", "user"]:
        print("abrioso")
    elif args[:2] in (["auth", "status"], ["repo", "view"]):
        pass
    elif args[:2] == ["pr", "list"]:
        print("https://github.com/abrioso/dotfiles-macos/pull/1")
    elif args[:2] in (["repo", "create"], ["repo", "edit"], ["pr", "create"]):
        record()
    else:
        sys.exit("Unexpected gh command")
else:
    if args[:1] == ["ls-remote"]:
        print(pathlib.Path(os.environ["PUBLICATION_TEST_REFS"]).read_text(), end="")
    elif args[:1] == ["push"] or args[:3] == ["-c", "core.hooksPath=/dev/null", "push"]:
        record()
    elif args and args[0] in ("status", "branch", "rev-list", "rev-parse", "remote", "merge-base", "config"):
        sys.exit(subprocess.call([os.environ["PUBLICATION_TEST_GIT"]] + args))
    else:
        sys.exit("Unexpected git command; network access is not permitted in this test")
'''
        for name in ("git", "gh"):
            path = binaries / name
            path.write_text("#!" + sys.executable + "\n" + stub)
            path.chmod(0o755)
        self.environment = dict(os.environ,
                                PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                                PUBLICATION_TEST_REFS=str(self.refs),
                                PUBLICATION_TEST_ACTIONS=str(self.actions),
                                PUBLICATION_TEST_GIT=self.real_git)

    def git(self, *args):
        command = subprocess.run([self.real_git, "-C", str(self.checkout), *args],
                                 text=True, capture_output=True)
        self.assertEqual(command.returncode, 0, command.stderr)
        return command.stdout.strip()

    def invoke(self, refs):
        self.refs.write_text("".join(sha + "\t" + ref + "\n" for sha, ref in refs))
        self.actions.write_text("")
        output = subprocess.run(["/bin/bash", str(self.checkout / "setup-scripts/publish.sh")],
                                env=self.environment, capture_output=True, text=True)
        return output, [json.loads(line) for line in self.actions.read_text().splitlines()]

    def test_unexpected_branches_rejected_before_publication(self):
        for name in ("unrelated", "feature/main", "main-extra"):
            for base in ("main", "develop"):
                with self.subTest(name=name, base=base):
                    output, actions = self.invoke([
                        (self.seed, "refs/heads/" + base),
                        (self.head, "refs/heads/" + name),
                    ])
                    self.assertEqual(output.returncode, 2, output.stderr)
                    self.assertIn("Unexpected remote branch", output.stderr)
                    self.assertEqual(actions, [])

    def test_empty_seed_and_known_feature_reruns_are_accepted(self):
        for refs in ([], [(self.seed, "refs/heads/main")],
                     [(self.seed, "refs/heads/develop")],
                     [(self.seed, "refs/heads/main"), (self.seed, "refs/heads/develop")],
                     [(self.seed, "refs/heads/main"), (self.previous, "refs/heads/feature/initial-macos")],
                     [(self.seed, "refs/heads/main"), (self.head, "refs/heads/feature/initial-macos")]):
            with self.subTest(refs=refs):
                output, actions = self.invoke(refs)
                self.assertEqual(output.returncode, 0, output.stderr)
                self.assertEqual(sum(item[0] == "git" and "push" in item for item in actions), 2)
                self.assertTrue(any(item[:3] == ["gh", "repo", "edit"] for item in actions))

    def test_unknown_divergent_feature_or_nonseed_base_is_rejected(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        divergent = self.git("commit-tree", tree, "-p", self.seed, "-m", "unrelated history")
        for refs in (
            [(self.seed, "refs/heads/main"), ("f" * 40, "refs/heads/feature/initial-macos")],
            [(self.seed, "refs/heads/main"), (divergent, "refs/heads/feature/initial-macos")],
            [(self.head, "refs/heads/main")],
            [(self.head, "refs/heads/feature/initial-macos")],
        ):
            with self.subTest(refs=refs):
                output, actions = self.invoke(refs)
                self.assertEqual(output.returncode, 2, output.stderr)
                self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()
