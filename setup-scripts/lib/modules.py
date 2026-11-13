"""Build a complete deployment before mutating user files."""
import os
from pathlib import Path

from .config import ConfigError, PREFERENCES
from .deployment import assert_safe, existing_text, marked_text
from .system import preference_state, run


def git_text(settings):
    sections = {}
    for key, value in settings.items():
        if value:
            section, name = key.split(".", 1)
            sections.setdefault(section, []).append((name, value))
    lines = []
    for section, entries in sections.items():
        lines.append("[" + section + "]")
        for name, value in entries:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append("\t" + name + ' = "' + escaped + '"')
    return "\n".join(lines) + "\n"


def desired_files(root, home, config):
    root, home = Path(root), Path(home)
    files = {}
    store = home / ".config/dotfiles-macos"
    modules = config["modules"]
    if "shell" in modules:
        if os.environ.get("ZDOTDIR") and Path(os.environ["ZDOTDIR"]) != home:
            raise ConfigError("Custom ZDOTDIR is not managed; integrate the shell profile manually.")
        for name in ("zshrc", "zprofile"):
            files[store / name] = (root / "shell" / name).read_text(encoding="utf-8")
            target = home / ("." + name)
            body = '[ -r "$HOME/.config/dotfiles-macos/' + name + '" ] && source "$HOME/.config/dotfiles-macos/' + name + '"'
            files[target] = marked_text(existing_text(target), body)
    if "shell" in modules or "pwsh" in modules:
        files[store / "theme.omp.json"] = (root / "themes/theme.omp.json").read_text(encoding="utf-8")
    if "pwsh" in modules:
        if os.environ.get("XDG_CONFIG_HOME") and Path(os.environ["XDG_CONFIG_HOME"]) != home / ".config":
            raise ConfigError("Custom XDG_CONFIG_HOME requires manual PowerShell integration.")
        files[store / "profile.ps1"] = (root / "powershell-profiles/profile.ps1").read_text(encoding="utf-8")
        target = home / ".config/powershell/profile.ps1"
        body = "$dotfilesProfile = Join-Path $HOME '.config/dotfiles-macos/profile.ps1'\nif (Test-Path -LiteralPath $dotfilesProfile) { . $dotfilesProfile }"
        files[target] = marked_text(existing_text(target), body)
    if "git" in modules:
        if os.environ.get("GIT_CONFIG_GLOBAL") or os.environ.get("GIT_CONFIG_COUNT"):
            raise ConfigError("Custom Git config environment requires manual integration.")
        files[store / "gitconfig"] = git_text(config["git"])
        target = home / ".gitconfig"
        existing = existing_text(target)
        # Keep existing XDG-only layouts explicit instead of changing precedence.
        xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))) / "git/config"
        if not target.exists() and xdg.exists():
            raise ConfigError("Existing XDG Git config detected; integrate it manually before applying Git.")
        if target.exists():
            result = run(["git", "config", "--file", target, "--list"])
            if result.returncode:
                raise ConfigError("Existing Git config cannot be parsed; no changes applied.")
        body = '[include]\n\tpath = "~/.config/dotfiles-macos/gitconfig"'
        files[target] = marked_text(existing, body)
    for path in files:
        assert_safe(path)
    return files


def prepare_preferences(config):
    if "macos" not in config["modules"]:
        return []
    pending = []
    for name, desired in config["macos"].items():
        domain, key = PREFERENCES[name]
        previous = preference_state(domain, key)
        if not previous["exists"] or previous["value"] != desired:
            pending.append({"name": name, "domain": domain, "key": key,
                            "previous": previous, "desired": desired})
    return pending


def apply_preferences(pending, deployment):
    if not pending:
        return
    deployment.record_preferences(pending)
    for item in pending:
        result = run(["/usr/bin/defaults", "write", item["domain"], item["key"],
                      "-bool", "true" if item["desired"] else "false"])
        if result.returncode:
            raise ConfigError("Preference write failed; consult the preference backup.")
        actual = preference_state(item["domain"], item["key"])
        if not actual["exists"] or actual["value"] != item["desired"]:
            raise ConfigError("Preference verification failed; consult the preference backup.")


def display_plan(config, catalog):
    from .config import packages
    return {
        "package_groups": config["package_groups"],
        "packages": packages(config, catalog),
        "modules": [name for name in ("shell", "pwsh", "git", "macos") if name in config["modules"]],
        "package_policy": "install-missing; no upgrade; no uninstall; no service start",
        "personal_values": "omitted",
        "possible_elevation": bool(packages(config, catalog)["casks"]),
    }
