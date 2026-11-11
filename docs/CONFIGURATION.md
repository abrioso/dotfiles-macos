# Configuration and operation

## First use

1. Check `uname -m` and `sw_vers -productVersion`; use Terminal without Rosetta.
2. Install Apple Command Line Tools with `xcode-select --install` if needed.
3. Obtain the repository and stay on the intended checkout. Before the first
   release, use the implementation/review branch indicated in the README.
4. Review and run `./setup-scripts/bootstrap.sh`. If Homebrew is missing, rerun
   with `--install-homebrew`. The official installer is downloaded to a file,
   verified using SHA-256 and only then executed. It may request sudo.
5. Run the printed `export PATH=...` command if needed. The script cannot change
   the environment of its parent terminal.
6. Run `./setup-scripts/configure.sh`. Arrows move, Space toggles, S saves and
   Q/Esc cancels without writing files. The window must be at least 35 by 8.
7. Edit `dotfiles-configurations/config.json` to set `user.name` and `user.email`.
   Empty fields preserve the existing Git identity.
8. Review `./setup-scripts/setup.sh --plan`, then apply with `./setup-scripts/setup.sh`.
9. Open a new terminal and run `./setup-scripts/verify.sh --check-packages`.

To create configuration without the TUI:

```sh
./setup-scripts/configure.sh --defaults
./setup-scripts/setup.sh --plan --json
./setup-scripts/setup.sh --yes
```

`--defaults` initializes missing files and preserves saved choices; it does not
reset settings to factory defaults. `--yes` accepts the dotfiles apply operation
but does not suppress prompts from Homebrew, macOS, installers or application
licenses. Do not run setup with sudo. If Python was installed through Homebrew,
a new terminal may need the PATH printed by bootstrap before Zsh configuration
has been applied.

## File model

`config.json.example` and `packages.json.example` are tracked. Copies without
`.example` are private and ignored by Git. Empty arrays mean no selection;
unknown values, duplicate keys and invalid dependencies fail validation.
A local catalog can remove packages from a group without changing the shared template.

The `pwsh` module requires the package group of the same name. Docker Desktop
and Colima are mutually exclusive selections. Changing the selection does not
migrate data from the previous runtime. Review existing installations and Docker
contexts manually before switching.

Settings are machine-specific. Do not put tokens in templates, the theme or
tracked profiles. Homebrew/GitHub/Microsoft/Tailscale credentials, SSH keys,
OneDrive authentication and rclone profiles are managed outside the repository.
The `data` group only installs rclone; it does not copy, sync or delete data.

## Profiles and Git

Deployed files:

| Destination | Content |
| --- | --- |
| `~/.config/dotfiles-macos/zprofile` | Native Homebrew environment |
| `~/.config/dotfiles-macos/zshrc` | Aliases, completion and prompt |
| `~/.config/dotfiles-macos/theme.omp.json` | Independent theme copy |
| `~/.zprofile`, `~/.zshrc` | Loader block; personal content preserved |
| `~/.config/dotfiles-macos/gitconfig` | Selected Git settings |
| `~/.gitconfig` | Managed `[include]` block; other settings preserved |
| `~/.config/dotfiles-macos/profile.ps1` | Optional PowerShell profile |
| `~/.config/powershell/profile.ps1` | PowerShell loader block shared across hosts |

Changes inside the markers are replaced on the next apply, after backup.
Content outside the markers is preserved. Symlinks in destinations or their
parent directories are rejected, as are incomplete or duplicate markers.
Custom `ZDOTDIR`, `XDG_CONFIG_HOME` and XDG-only Git layouts may require manual
integration, depending on the module.

The Git include is appended on first apply. It may override earlier values
for the same keys without deleting the original text. Included files or later
settings may take precedence; `verify` detects that drift. Neither `core.ignorecase`
nor `core.filemode` is imposed. Explicitly load private settings from a local
file outside the managed block.

Manually select **CaskaydiaCove Nerd Font** in Terminal/iTerm2 or VS Code settings
if desired. The script installs the font when selected but does not replace
terminal profiles or preferences. Existing VS Code/PowerShell host profiles may
change the prompt after the common profile; check both during acceptance.

## PowerShell and Azure

The catalog uses `brew "powershell"`, currently a Homebrew community build.
For Microsoft support, prefer the signed/notarized PKG described in the
[official documentation](https://learn.microsoft.com/powershell/scripting/install/install-powershell-on-macos).
In that case, install the PKG manually and remove `powershell` from the `formulae`
list in the local `pwsh` package group, keeping `oh-my-posh` and the `pwsh` module.
Do not overlay existing installations from different sources without reviewing them.

Azure CLI uses the `azure-cli` cask. Azure Developer CLI (`azd`) is outside this
initial version. Migrating an older formula-based Azure CLI installation requires
explicit intervention following Microsoft's documentation.

## Docker

Docker Desktop installs the application; initial launch, licensing, permissions,
resources and automatic startup are configured manually. This repository does
not launch any `akb-docker-stack` containers.

Colima installs `colima`, `docker` and `docker-compose` without creating/starting
a VM. For first use, review the intended resources and run `colima start`.
According to Homebrew's instructions, the Compose plugin may need
`cliPluginsExtraDirs` in `~/.docker/config.json`:

```json
{
  "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]
}
```

On Intel, use `/usr/local/lib/docker/cli-plugins`. **Merge the key into the
existing JSON; do not replace the file**, which may contain authentication and
other contexts. Check `docker context ls`, `docker info` and `docker compose version`
before using stacks. This version's diagnostics check package presence, not daemon
health or equivalence between runtimes.

## Updates

```sh
./setup-scripts/update.sh
./setup-scripts/setup.sh --plan
./setup-scripts/setup.sh
```

`update` requires a clean working tree, an attached branch and an upstream on
`origin`. It fetches and fast-forwards that branch; divergence causes failure.
It does not switch branches or reset local JSON. Review template differences
manually and incorporate only what is needed. Package upgrades are separate,
for example `brew outdated` followed by `brew upgrade <package>` after review.
The repository does not run `brew bundle cleanup`.

## Diagnostics

`verify --json` omits identity values and file contents. Package and key names
are shown. Reports are not created automatically.

| Exit code | Meaning |
| --- | --- |
| 0 | All requested checks are conclusive and conformant |
| 1 | At least one confirmed drift finding |
| 2 | Invalid configuration or preflight failure |
| 3 | No confirmed drift, but some checks are inconclusive |
| 130 | Interrupted operation |

Without `--check-packages`, selected packages remain inconclusive. With that
option, only local Homebrew lists are queried, without auto-update.
Exact versions, `.app` bundle integrity, licenses, selected fonts, authentication,
connectivity and service state are not checked.
