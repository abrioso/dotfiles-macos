# dotfiles-macos

Modular Mac configuration based on
[dotfiles-windows](https://github.com/abrioso/dotfiles-windows): per-machine choices,
a toggle UI, preview before applying, backups and drift diagnostics.
Uses Homebrew, Zsh and optional PowerShell with the same Oh My Posh theme.

**Status:** initial implementation on `feature/initial-macos`, targeting `develop`.
`main` contains only the repository seed. No release has been accepted on a
physical Mac yet. The implementation is published in
[PR #1 to develop](https://github.com/abrioso/dotfiles-macos/pull/1).
Check that PR's validation results before merging; see [Gitflow](docs/GITFLOW.md).

## Getting started

Initial target: **macOS 15+**, Apple Silicon or Intel, using a native terminal
without Rosetta. Git/Apple Command Line Tools, Homebrew and Python 3.9+ are
required. Bootstrap guides prerequisite setup and installs Homebrew only with
an explicit option. Intel may have additional package availability/support limits.

Keep Git repositories in `~/workspace`. If you received the delivery archive,
extract it there and enter `~/workspace/dotfiles-macos`.
To evaluate the published initial implementation:

```sh
xcode-select --install  # Only if Command Line Tools are missing.
mkdir -p ~/workspace && cd ~/workspace
git clone --branch feature/initial-macos https://github.com/abrioso/dotfiles-macos.git
cd dotfiles-macos
./setup-scripts/bootstrap.sh
# If needed, review and run:
./setup-scripts/bootstrap.sh --install-homebrew
# Run the export PATH command printed by bootstrap, if needed.
./setup-scripts/configure.sh
./setup-scripts/setup.sh --plan
./setup-scripts/setup.sh
./setup-scripts/verify.sh --check-packages
```

In the TUI, use **arrow keys**, **Space** to toggle, **S** to save and **Q/Esc**
to cancel. Saving does not install software. Setup asks for confirmation;
`--yes` skips only that confirmation. Do not run with sudo.

The template leaves `user.name` and `user.email` empty. Fill them in the local
`dotfiles-configurations/config.json` before applying, if desired.

## Operations

| Command | Result |
| --- | --- |
| `configure.sh` | Edits selections with toggles; saves only when requested |
| `configure.sh --defaults` | Initializes missing files; preserves existing choices |
| `setup.sh --plan [--json]` | Validates and previews intent without changes or external queries |
| `setup.sh [--yes]` | Installs missing packages and applies this checkout |
| `verify.sh [--json] [--check-packages]` | Detects drift without applying corrections |
| `update.sh` | Updates only the current branch, by fast-forward |

All commands are in `setup-scripts/`. A plan does not guarantee installation
will succeed: permissions, existing files and package availability are checked
during apply. Packages are not implicitly upgraded or removed.

## Initial selection

Enabled by default: `base`, `terminal`, `dev`; modules `shell` and `git`.
Optional groups cover PowerShell, browsers, Microsoft 365, Docker Desktop or
Colima, Azure CLI, multimedia, power-user tools, Tailscale, Yubico, Google Drive,
Windows App and rclone.

Deselecting an option prevents future application but does not remove previously
installed software or configuration. Docker Desktop and Colima cannot both be
selected. No runtime, service or container is started automatically.

Finder preferences are optional. Terminal font selection, initial application
launch, macOS permissions and authentication are manual steps.
Security policies and MDM configuration are not changed.

## Documentation and validation

- [Architecture and Windows equivalents](docs/ARCHITECTURE.md)
- [Configuration, installation and operation](docs/CONFIGURATION.md)
- [Rollback and removal](docs/ROLLBACK.md)
- [Gitflow and initial publication](docs/GITFLOW.md)
- [Mac acceptance checklist](docs/ACCEPTANCE.md)
- [Validation results and limitations](docs/VALIDATION.md)

```sh
./tests/validate.sh
```

Tests do not provision the host. CI is configured for Linux, macOS Apple Silicon
and macOS Intel. Enable local hooks and branch rules as described in the Gitflow
guide. Use Conventional Commits and `vYYYY.MM.N` versions.
