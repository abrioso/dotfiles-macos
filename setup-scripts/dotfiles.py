#!/usr/bin/env python3
"""macOS dotfiles CLI. No third-party Python dependencies."""
import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True  # Plan/verify must not create Python cache files.
from lib.config import ConfigError, PREFERENCES, brewfile, load, load_for_configure, packages
from lib.deployment import Deployment, assert_safe
from lib.modules import apply_preferences, desired_files, display_plan, prepare_preferences
from lib.system import homebrew, installed_packages, preference_state, require_mac, run

ROOT = Path(__file__).resolve().parent.parent


def configure(args):
    config, catalog = load_for_configure(ROOT)
    if not args.defaults:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ConfigError("A terminal is required; use configure --defaults to initialize explicitly.")
        from lib.tui import choose
        import curses
        try:
            config = choose(config, catalog)
        except curses.error as exc:
            raise ConfigError("Terminal initialization failed; use a full terminal or configure --defaults.") from exc
        if config is None:
            print("Cancelled; no files changed.")
            return 0
    deploy = Deployment(Path.home())
    directory = ROOT / "dotfiles-configurations"
    paths = [directory / name for name in ("config.json", "packages.json")]
    for path in paths:
        assert_safe(path)
    try:
        for path, data in zip(paths, (config, catalog)):
            deploy.write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    finally:
        if deploy.backup_dir:
            print("Configuration backup: " + str(deploy.backup_dir))
    print("Configuration saved. Preview: ./setup-scripts/setup.sh --plan")
    return 0


def setup(args):
    config, catalog = load(ROOT)
    if args.plan:
        plan = display_plan(config, catalog)
        print(json.dumps(plan, indent=2) if args.json else
              "Groups: " + (", ".join(plan["package_groups"]) or "none") + "\n" +
              "Formulae: " + (", ".join(plan["packages"]["formulae"]) or "none") + "\n" +
              "Casks: " + (", ".join(plan["packages"]["casks"]) or "none") + "\n" +
              "Modules: " + (", ".join(plan["modules"]) or "none") + "\n" +
              "No changes applied. Live files and package availability are checked during apply.")
        return 0
    if args.json:
        raise ConfigError("--json is supported only with --plan.")
    require_mac()
    if not args.yes:
        if not sys.stdin.isatty() or input("Apply this local configuration? [y/N] ").lower() != "y":
            print("Cancelled; no changes applied.")
            return 0
    # Resolve every file and preference conflict before requesting installation.
    files = desired_files(ROOT, Path.home(), config)
    pending = prepare_preferences(config)
    text = brewfile(config, catalog)
    deploy = Deployment(Path.home())
    try:
        if text:
            brew = homebrew()
            with tempfile.TemporaryDirectory(prefix="dotfiles-macos-") as temporary:
                path = Path(temporary) / "Brewfile"
                path.write_text(text, encoding="utf-8")
                environment = dict(os.environ, HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_ANALYTICS="1")
                # Inherit stdin for Homebrew/cask authentication. Never capture credentials.
                result = subprocess.run([str(brew), "bundle", "install", "--no-upgrade", "--file", str(path)],
                                        env=environment, check=False)
                if result.returncode:
                    raise ConfigError("Package installation failed. No dotfiles applied; installed packages remain.")
                installed = installed_packages(brew)
                for kind, tokens in packages(config, catalog).items():
                    if not set(tokens).issubset(installed[kind]):
                        raise ConfigError("Package installation did not satisfy the selection; dotfiles not applied.")
        for path, text in files.items():
            changed = deploy.write(path, text)
            print(("Updated: " if changed else "Unchanged: ") + str(path.relative_to(Path.home())))
        apply_preferences(pending, deploy)
    finally:
        if deploy.backup_dir:
            print("Backup: " + str(deploy.backup_dir))
    print("Apply complete. Open a new terminal, then run ./setup-scripts/verify.sh --check-packages.")
    if "colima" in config["package_groups"]:
        print("Colima is not started. See docs/CONFIGURATION.md for Docker Compose setup.")
    if "macos" in config["modules"]:
        print("Finder changes may require a new login. Finder was not restarted.")
    return 0


def verify(args):
    config, catalog = load(ROOT)
    checks = []

    def record(name, status):
        checks.append({"check": name, "status": status})

    if platform.system() != "Darwin":
        record("platform", "inconclusive")
    try:
        files = desired_files(ROOT, Path.home(), config)
        for path, text in files.items():
            matches = path.is_file() and path.read_bytes() == text.encode("utf-8") and path.stat().st_nlink == 1
            record("file:" + str(path.relative_to(Path.home())), "ok" if matches else "drift")
    except (ConfigError, OSError, UnicodeError):
        record("file-preflight", "inconclusive")
    if "git" in config["modules"]:
        for key, expected in config["git"].items():
            if expected:
                try:
                    result = run(["git", "config", "--global", "--includes", "--get", key])
                    status = "inconclusive" if result.returncode not in (0, 1) else (
                        "ok" if result.returncode == 0 and result.stdout.rstrip("\n") == expected else "drift")
                except ConfigError:
                    status = "inconclusive"
                record("git:" + key, status)
    if config["package_groups"]:
        if args.check_packages and platform.system() == "Darwin":
            try:
                installed = installed_packages(homebrew())
                for kind, tokens in packages(config, catalog).items():
                    for token in tokens:
                        record(kind + ":" + token, "ok" if token in installed[kind] else "drift")
            except ConfigError:
                record("packages", "inconclusive")
        else:
            record("packages", "inconclusive")
    if "macos" in config["modules"]:
        for name, expected in config["macos"].items():
            try:
                if platform.system() != "Darwin":
                    raise ConfigError("macOS required")
                state = preference_state(*PREFERENCES[name])
                status = "ok" if state["exists"] and state["value"] == expected else "drift"
            except ConfigError:
                status = "inconclusive"
            record("macos:" + name, status)
    exit_code = 1 if any(x["status"] == "drift" for x in checks) else (
        3 if any(x["status"] == "inconclusive" for x in checks) else 0)
    if args.json:
        print(json.dumps({"checks": checks, "exit_code": exit_code}, indent=2))
    else:
        for check in checks:
            print(check["status"].upper() + " " + check["check"])
    return exit_code


def update(_args):
    def git(*arguments):
        result = run(["git", "-C", ROOT, *arguments])
        if result.returncode:
            raise ConfigError("Git update failed; inspect repository/upstream without applying setup.")
        return result.stdout.strip()

    if git("status", "--porcelain", "--untracked-files=all"):
        raise ConfigError("Working tree is not clean; commit or preserve changes before updating.")
    branch = git("symbolic-ref", "--short", "HEAD")
    remote = git("config", "--get", "branch." + branch + ".remote")
    merge_ref = git("config", "--get", "branch." + branch + ".merge")
    if remote != "origin" or not merge_ref.startswith("refs/heads/"):
        raise ConfigError("A branch upstream on origin is required; configure it explicitly.")
    git("fetch", "--no-tags", "origin", merge_ref)
    git("merge", "--ff-only", "FETCH_HEAD")
    print("Repository updated. Local configuration preserved. Setup was not run.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    conf = commands.add_parser("configure")
    conf.add_argument("--defaults", action="store_true", help="Create missing configuration; preserve saved choices")
    conf.set_defaults(function=configure)
    apply = commands.add_parser("setup")
    apply.add_argument("--plan", action="store_true", help="Validate and preview; no writes, downloads or probes")
    apply.add_argument("--json", action="store_true")
    apply.add_argument("--yes", action="store_true", help="Apply without the dotfiles confirmation")
    apply.set_defaults(function=setup)
    check = commands.add_parser("verify")
    check.add_argument("--json", action="store_true")
    check.add_argument("--check-packages", action="store_true", help="Query local Homebrew package lists, without update")
    check.set_defaults(function=verify)
    refresh = commands.add_parser("update")
    refresh.set_defaults(function=update)
    args = parser.parse_args(argv)
    try:
        return args.function(args)
    except (ConfigError, OSError, UnicodeError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": "Configuration or preflight failed; run without --json for details.", "exit_code": 2}))
        else:
            print("Error: " + str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted. Completed changes may remain; consult the backup path.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
