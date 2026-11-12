"""Strict local configuration; templates are read-only defaults."""
import json
import re
from pathlib import Path

MODULES = ("shell", "git", "pwsh", "macos")
GIT_KEYS = {
    "user.name", "user.email", "core.autocrlf", "core.safecrlf",
    "init.defaultBranch", "pull.ff", "push.default", "core.editor",
    "alias.st", "alias.co", "alias.br", "alias.ci", "alias.df", "alias.lg",
}
PREFERENCES = {
    "show_file_extensions": ("NSGlobalDomain", "AppleShowAllExtensions"),
    "show_path_bar": ("com.apple.finder", "ShowPathbar"),
    "show_status_bar": ("com.apple.finder", "ShowStatusBar"),
}
TOKEN = re.compile(r"^[a-z0-9][a-z0-9+@._-]*$")


class ConfigError(ValueError):
    """An actionable configuration or preflight error."""


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("Duplicate JSON key; correct the configuration.")
        result[key] = value
    return result


def read_json(path):
    from .deployment import assert_safe
    assert_safe(path)
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=object_pairs)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ConfigError("Cannot read valid JSON: " + Path(path).name) from exc


def selected_list(value, allowed, label):
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ConfigError(label + " must be an array of strings.")
    if len(set(value)) != len(value) or any(x not in allowed for x in value):
        raise ConfigError(label + ": unknown/duplicate selection. Available: " + ", ".join(allowed))


def validate(config, catalog):
    if not isinstance(catalog, dict) or not catalog:
        raise ConfigError("Package catalog must be a non-empty object.")
    for group, data in catalog.items():
        if not TOKEN.fullmatch(group) or not isinstance(data, dict):
            raise ConfigError("Invalid package group.")
        if set(data) != {"description", "formulae", "casks"}:
            raise ConfigError("A package group needs description, formulae and casks.")
        if not isinstance(data["description"], str) or any(ord(c) < 32 for c in data["description"]):
            raise ConfigError("Invalid group description.")
        for kind in ("formulae", "casks"):
            entries = data[kind]
            if (not isinstance(entries, list)
                    or any(not isinstance(x, str) or not TOKEN.fullmatch(x) for x in entries)):
                raise ConfigError("Invalid package token; only official unqualified tokens are supported.")
            if len(entries) != len(set(entries)):
                raise ConfigError("Duplicate package in a group.")
    keys = {"schema_version", "package_groups", "modules", "git", "macos"}
    if not isinstance(config, dict) or set(config) != keys:
        raise ConfigError("Configuration must contain exactly: " + ", ".join(sorted(keys)))
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ConfigError("Unsupported schema_version; expected 1.")
    selected_list(config["package_groups"], catalog, "package_groups")
    selected_list(config["modules"], MODULES, "modules")
    groups = config["package_groups"]
    if "docker-desktop" in groups and "colima" in groups:
        raise ConfigError("Select only one container runtime: docker-desktop or colima.")
    if "pwsh" in config["modules"] and "pwsh" not in groups:
        raise ConfigError("The pwsh module requires the pwsh package group.")
    settings = config["git"]
    if not isinstance(settings, dict) or any(key not in GIT_KEYS for key in settings):
        raise ConfigError("Unsupported Git key; use local Git configuration for other settings.")
    for key, value in settings.items():
        if not isinstance(value, str) or any(ord(c) < 32 for c in value):
            raise ConfigError("Git values must be single-line strings without control characters.")
        if key.startswith("alias.") and value.lstrip().startswith("!"):
            raise ConfigError("Shell aliases are not supported in the managed Git configuration.")
    if not isinstance(config["macos"], dict) or set(config["macos"]) != set(PREFERENCES):
        raise ConfigError("Unknown or missing macOS preference.")
    if any(type(x) is not bool for x in config["macos"].values()):
        raise ConfigError("macOS preferences must be booleans.")
    return config, catalog


def load(root):
    from .deployment import assert_safe
    directory = Path(root) / "dotfiles-configurations"
    paths = [directory / name for name in ("config.json", "packages.json")]
    for path in paths:
        assert_safe(path)
    if any(not p.is_file() for p in paths):
        raise ConfigError("Local configuration is missing. Run ./setup-scripts/configure.sh first.")
    return validate(*(read_json(path) for path in paths))


def load_for_configure(root):
    from .deployment import assert_safe
    directory = Path(root) / "dotfiles-configurations"
    paths = [directory / name for name in ("config.json", "packages.json")]
    for path in paths:
        assert_safe(path)
    return validate(*(read_json(p if p.exists() else Path(str(p) + ".example")) for p in paths))


def packages(config, catalog):
    result = {"formulae": [], "casks": []}
    for group in config["package_groups"]:
        for kind in result:
            for token in catalog[group][kind]:
                if token not in result[kind]:
                    result[kind].append(token)
    return result


def brewfile(config, catalog):
    selected = packages(config, catalog)
    return "".join(keyword + " " + json.dumps(token) + "\n"
                   for kind, keyword in (("formulae", "brew"), ("casks", "cask"))
                   for token in selected[kind])
