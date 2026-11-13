# Architecture and relationship to dotfiles-windows

Reviewed reference: `abrioso/dotfiles-windows`, branch `develop`, commit
`e53a286` (reviewed on 2026-11-11). The macOS implementation is independent;
it does not execute Windows scripts or share local settings between platforms.
The theme in `themes/theme.omp.json` was reused from
`poshthemes/jandedobbeleer.omp.json` at that revision.

## Functional mapping

| Windows | macOS |
| --- | --- |
| PowerShell orchestrator | Python 3.9+ standard library; Bash 3.2 entry points |
| Winget package groups | Homebrew Bundle; JSON package-group catalog |
| Toggle UI | Curses: arrows, Space, save or cancel |
| PowerShell as the primary shell | Zsh; optional PowerShell |
| Windows Terminal + Nerd Font + Oh My Posh | Terminal/iTerm2 + Nerd Font + the same Oh My Posh theme |
| Private JSON and tracked templates | Same principle, with two local JSON files |
| Separate apply, update and diagnostics | `setup.sh`, `update.sh`, `verify.sh` |
| Profiles copied to local storage | Copies under `~/.config/dotfiles-macos`; profile loader blocks |
| Gitflow and CI | `main`, `develop`, feature branches, PRs and Linux/macOS tests |
| WSL, Hyper-V, Sandbox, RSAT | No automatic translation; not natively applicable |
| Docker Desktop | Docker Desktop or Colima, mutually exclusive |
| Power BI Desktop | Outside the catalog; use the web service or remote Windows as needed |

Python provides JSON validation, atomic file publication and failure testing
without external dependencies. Bash handles entry points and bootstrap; Zsh
remains the user's shell. This avoids requiring PowerShell to prepare a Mac.

## Components

- `setup-scripts/lib/config.py`: strict parsing, dependencies and Brewfile generation.
- `setup-scripts/lib/tui.py`: in-memory selection; writes only when S is pressed.
- `setup-scripts/lib/deployment.py`: independent copies, markers and backups.
- `setup-scripts/lib/modules.py`: file and preference preparation.
- `setup-scripts/lib/system.py`: external commands and Homebrew detection.
- `setup-scripts/dotfiles.py`: orchestration and exit codes.
- `dotfiles-configurations`: templates and Git-ignored local copies.
- `shell`, `powershell-profiles`, `themes`: content to deploy, without symlinks.

## Decisions and limitations

The initial target is macOS 15 or newer, prioritizing Apple Silicon. Intel is
detected and has its own CI job, but package availability depends on current
Homebrew and vendor support. Running under Rosetta is rejected.
Rosetta is not installed automatically. The owner's Mac model and macOS version
have not yet been confirmed; compatibility must be checked during acceptance.

The initial selection includes `base`, `terminal`, `dev` and modules `shell`, `git`.
Application, Docker, identity, synchronization and data groups are optional.
Finder preferences are optional and limited to three booleans. There are no
automatic changes to FileVault, Gatekeeper, SIP, firewall, SSH, MDM or login.

`setup` installs missing packages with `brew bundle --no-upgrade`, then applies
files and preferences. Installation failures prevent the file phase.
The complete apply operation is not a transaction: packages already installed
and changes completed before a failure remain, with backup information for files.

Deselecting a group prevents future application. It does not uninstall software,
remove an existing loader block or restore preferences. Removal is an explicit
operation described in `ROLLBACK.md`. This preserves application state and
settings the user may still need.

The Brewfile is generated in a temporary directory from validated tokens and
removed afterward. Arbitrary Ruby, taps and executable catalog content are not
accepted. Application versions are not pinned; `--no-upgrade` prevents implicit
upgrades but does not make installations bit-for-bit reproducible.

`plan` shows validated intent without inspecting live state. `verify` reads
live state without correcting it. Updating the checkout does not change deployed
copies. Applying the checkout does not update it. Prerequisite bootstrap is also separate.
