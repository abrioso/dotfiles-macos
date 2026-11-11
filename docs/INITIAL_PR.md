Adds the macOS companion to dotfiles-windows, using its current develop branch
as the functional reference. Users can save package/module selections with a
toggle UI, preview a validated plan, apply the current checkout with backups,
and diagnose drift separately from repository updates.

Homebrew groups cover development tools and optional Microsoft applications,
PowerShell, remote access and container runtimes. Zsh is the primary shell;
Docker Desktop and Colima are mutually exclusive selections. No runtime is
started automatically. Local JSON and personal identity remain untracked.

Validation: standard-library regression tests and shell/static checks are
included, with CI for Linux and macOS ARM/Intel. Tests cover preservation,
idempotency, preflight failures, read-only plans, diagnostics and Gitflow guards.
See docs/VALIDATION.md for the actual local results and remaining checks.

Physical Mac acceptance remains pending. Homebrew packages are not version
locked; partial package installations are not rolled back. Existing symlinked
profiles and custom shell/XDG layouts require explicit integration. The manual
rollback procedure preserves later user changes.
