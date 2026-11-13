# Gitflow and publication

`main` contains accepted releases only. `develop` integrates the next cycle.
Normal work uses `feature/*` or `fix/*` from `develop`, with a PR to `develop`.
Releases use `release/vYYYY.MM.N`, a PR to `main`, a tag after acceptance and
reconciliation of release-only changes into `develop`. Hotfixes start at `main`
and must reach both branches. Never force-push to the base branches.

At initialization, `main` and `develop` point to the same README-only commit.
All implementation work is on `feature/initial-macos`. Publishing that initial
commit to both branches is the only bootstrap exception.

## Publishing the prepared package

The delivery package contains a complete local Git repository, including all
three branches. Extract it, enter `dotfiles-macos` and run with GitHub CLI installed:

```sh
gh auth login --hostname github.com
gh auth setup-git --hostname github.com
./setup-scripts/publish.sh
```

The script checks the `abrioso` account, origin, clean working tree and initial
history. It creates `abrioso/dotfiles-macos` as **private** if absent, publishes
the initial base branches and feature, and opens a PR to `develop`. Incompatible
remote work causes it to stop without overwriting anything. It does not merge,
create tags or publish releases. Making the repository public requires an explicit
visibility change by the owner after review. If creating the repository manually,
leave it empty.

A network failure can leave some steps completed. The script can be rerun while
`main` and `develop` still point to the initial commit; do not use it after the
first merge into `develop`. It reuses an existing open PR.
Every remote branch is checked: only seed-valued `main`/`develop` and an existing
`feature/initial-macos` at a known ancestor of the local feature are accepted.
An unrelated branch, an unknown/divergent feature commit or a non-empty remote
without a seed base branch stops publication before any push or repository edit.

## Recommended protections

Configure server-side rules for `main` and `develop`: require a PR, prohibit
force-push/deletion and require `Validate (ubuntu-latest)`, `Validate (macos-15)`
and `Validate (macos-15-intel)` after their first run. Rule availability for
private repositories depends on the GitHub plan. Server-side protections must
not be assumed to exist until verified.

Install hooks only in this clone:

```sh
git config --local core.hooksPath git-hooks
```

`pre-push` blocks the full refs `refs/heads/main` and `refs/heads/develop`; it does
not block `feature/main` or a tag named `main`. `pre-commit` checks whitespace and
prevents accidental staging of local JSON and credential filename patterns.
Hooks can be bypassed and do not replace server-side rules or secret review.

Actions use read-only permissions, a commit-pinned checkout action and Dependabot
updates targeting `develop`. Tests use temporary directories without applying
dotfiles to the runner. The matrix does not replace acceptance in a real Mac account.
