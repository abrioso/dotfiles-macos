"""Bounded external commands and native Homebrew selection."""
import os
import platform
import plistlib
import subprocess
from pathlib import Path

from .config import ConfigError


def run(args, timeout=60):
    environment = dict(os.environ, HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_ANALYTICS="1", LC_ALL="C")
    try:
        return subprocess.run([str(x) for x in args], text=True, capture_output=True,
                              timeout=timeout, env=environment, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ConfigError("Command unavailable or timed out: " + str(args[0])) from exc


def require_mac():
    if platform.system() != "Darwin":
        raise ConfigError("Applying configuration requires macOS. Plan and tests work on other systems.")
    if os.geteuid() == 0:
        raise ConfigError("Run as the signed-in user, without sudo.")
    major = int(platform.mac_ver()[0].split(".")[0])
    if major < 15:
        raise ConfigError("This initial baseline requires macOS 15 or newer.")
    translated = run(["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"])
    if translated.returncode == 0 and translated.stdout.strip() == "1":
        raise ConfigError("Open Terminal natively, without Rosetta, before continuing.")


def homebrew():
    machine = platform.machine()
    if machine not in ("arm64", "x86_64"):
        raise ConfigError("Unsupported architecture.")
    prefix = "/opt/homebrew" if machine == "arm64" else "/usr/local"
    brew = Path(prefix) / "bin/brew"
    if not brew.is_file():
        raise ConfigError("Native Homebrew is missing. Run ./setup-scripts/bootstrap.sh.")
    result = run([brew, "--prefix"])
    if result.returncode or result.stdout.strip() != prefix:
        raise ConfigError("Homebrew prefix mismatch; inspect the installation manually.")
    return brew


def installed_packages(brew):
    result = {}
    for kind, flag in (("formulae", "--formula"), ("casks", "--cask")):
        query = run([brew, "list", flag, "-1"])
        if query.returncode:
            raise ConfigError("Cannot query installed Homebrew packages.")
        result[kind] = set(query.stdout.splitlines())
    return result


def preference_state(domain, key):
    # Export a typed plist instead of parsing localized read/read-type messages.
    query = run(["/usr/bin/defaults", "export", domain, "-"])
    label = domain + "/" + key
    if query.returncode:
        detail = (query.stderr.strip() or query.stdout.strip() or "No diagnostic output")[:1000]
        raise ConfigError("Unable to query macOS preference " + label
                          + " (exit " + str(query.returncode) + "): " + detail)
    try:
        preferences = plistlib.loads(query.stdout.encode("utf-8"))
    except (ValueError, plistlib.InvalidFileException) as exc:
        raise ConfigError("Invalid preference plist for " + label) from exc
    if not isinstance(preferences, dict):
        raise ConfigError("Expected a preference dictionary for " + label)
    if key not in preferences:
        return {"exists": False}
    value = preferences[key]
    if type(value) is not bool:
        raise ConfigError("Existing preference " + label + " is not a boolean; inspect it manually.")
    return {"exists": True, "value": value}
