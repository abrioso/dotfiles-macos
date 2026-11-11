# Initial validation evidence

Date: 2026-11-11. Local execution environment: Linux, Python 3.12.14,
the environment's Zsh and ShellCheck 0.11.0. No test applied settings to the
user's Mac, started runtimes or installed packages from the catalog.

## Completed

- **30 automated tests passed**, including a real pseudo-terminal TUI,
  cancellation without writes, saved toggles, strict validation, opt-outs,
  read-only plans/diagnostics without identity disclosure, independent copies,
  idempotency, backups, publication failures, symlinks/hardlinks, Git integration,
  installation failure before apply and fast-forward/divergent Git updates.
- Python syntax analysis using the 3.9 grammar; valid template and theme JSON.
- Bash/POSIX shell and Zsh syntax, ShellCheck without findings and Git whitespace checks.
- **34 unique catalog tokens confirmed** through the official Homebrew API, with
  no disabled/deprecated state in the observed responses. Evidence is recorded in
  `package-catalog-validation.json`. This checks availability, not installation
  or compatibility with every Mac model/macOS version.
- Homebrew installer retrieved from commit
  `7986efac25016e41eed7e471666140c06f9d97cf`; confirmed SHA-256:
  `5f333bbe53bc490e51e7ccb1df8779b3dd6ee73a1a7379efda216edb08ccb148`.

## Publication

- Private repository created by the owner; publication completed on 2026-11-11.
- `main` and `develop` initialized with only the README; implementation submitted
  in [PR #1](https://github.com/abrioso/dotfiles-macos/pull/1), from
  `feature/initial-macos` to `develop`, without a merge or release.
- The initially published implementation tree matched the locally validated tree:
  `ab24553bc6f6006b9c52ff27c2d29e927a1fe44a`. Documentation was subsequently updated
  to record publication, and repository content was translated into English.
- The CI matrix was triggered. Check the PR's checks for the current result.

## Pending

- Completion of the GitHub CI matrix.
- Actual macOS Apple Silicon/Intel and PowerShell validation. CI includes
  PowerShell parsing, but the executable was unavailable in the local environment.
- Mac acceptance, including font selection, terminal profiles, applications,
  permissions, any Docker runtime and restoration according to `ACCEPTANCE.md`.
- Configuration/verification of GitHub branch protection rules.

No release tag has been created. These tests do not establish compatibility with
all macOS systems or replace review and acceptance of the published commit.

## Technical sources consulted

- [Homebrew: installation and platforms](https://docs.brew.sh/Installation)
- [Homebrew: Bundle and the absence of a lockfile](https://docs.brew.sh/Brew-Bundle-and-Brewfile)
- [Homebrew: formula/cask API](https://formulae.brew.sh/docs/api/)
- [Homebrew: Docker Compose plugin](https://formulae.brew.sh/formula/docker-compose)
- [Microsoft: PowerShell on macOS](https://learn.microsoft.com/powershell/scripting/install/install-powershell-on-macos)
- [Microsoft: PowerShell through Homebrew](https://learn.microsoft.com/en-us/powershell/scripting/install/alternate-install-methods)
- [Microsoft: Azure CLI on macOS](https://learn.microsoft.com/cli/azure/install-azure-cli-macos)
- [GitHub: runner images](https://github.com/actions/runner-images)

These sources resolved current packaging changes and confirmed CI matrix labels.
Recheck them when updating prerequisites, packages or supported macOS versions.
