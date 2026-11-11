#!/bin/bash
# Publish only the reviewed initial Gitflow history. Requires authenticated gh/git.
set -euo pipefail
if [ "$#" -ne 0 ]; then echo 'Usage: ./setup-scripts/publish.sh' >&2; exit 2; fi
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
target=abrioso/dotfiles-macos
feature=feature/initial-macos
command -v gh >/dev/null 2>&1 || { echo 'Install GitHub CLI first: brew install gh' >&2; exit 2; }
gh auth status --hostname github.com >/dev/null 2>&1 || {
    echo 'Authenticate first: gh auth login --hostname github.com' >&2; exit 2;
}
if [ "$(gh api user --jq .login)" != abrioso ]; then
    echo 'Use the abrioso GitHub account for this initial publication.' >&2; exit 2
fi
if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
    echo 'Commit or preserve pending changes before publication.' >&2; exit 2
fi
if [ "$(git branch --show-current)" != "$feature" ]; then
    echo "Switch explicitly to $feature before publication." >&2; exit 2
fi
seed="$(git rev-list --max-parents=0 HEAD)"
if [ "$(git rev-parse main)" != "$seed" ] || [ "$(git rev-parse develop)" != "$seed" ]; then
    echo 'Initial branch invariant failed; do not use this script for later releases.' >&2; exit 2
fi
if [ "$(git remote get-url origin)" != "https://github.com/$target.git" ]; then
    echo 'Origin mismatch; inspect the remote manually.' >&2; exit 2
fi
if ! gh repo view "$target" --json name >/dev/null 2>&1; then
    gh repo create "$target" --private --description 'Modular macOS dotfiles based on dotfiles-windows; Gitflow, Homebrew, Zsh and optional PowerShell.'
fi
# Existing repositories are accepted only when empty or at this exact seed.
remote_heads="$(git ls-remote --heads origin)"
while read -r remote_sha remote_ref; do
    case "$remote_ref" in
        refs/heads/main|refs/heads/develop)
            if [ "$remote_sha" != "$seed" ]; then
                echo 'Remote main/develop already contain other work; stopping without overwrite.' >&2; exit 2
            fi ;;
    esac
done <<< "$remote_heads"
if [ -n "$remote_heads" ] && ! printf '%s\n' "$remote_heads" | grep -Eq 'refs/heads/(main|develop)$'; then
    echo 'Repository has an unexpected history; inspect it before publication.' >&2; exit 2
fi
# One-time README-only initialization, before activating the local branch guard.
git -c core.hooksPath=/dev/null push --atomic origin main develop
gh repo edit "$target" --default-branch main
git config --local core.hooksPath git-hooks
git push -u origin "$feature"
existing_pr="$(gh pr list --repo "$target" --base develop --head "$feature" --state open --json url --jq '.[0].url // empty')"
if [ -n "$existing_pr" ]; then
    printf '%s\n' "$existing_pr"
else
    gh pr create --repo "$target" --base develop --head "$feature" \
        --title 'feat: add modular macOS dotfiles baseline' \
        --body-file docs/INITIAL_PR.md
fi
echo 'Published for review. Configure branch rules described in docs/GITFLOW.md before merging.'
