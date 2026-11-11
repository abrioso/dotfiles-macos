# Agent instructions

Follow Gitflow: feature/fix branches start at `develop` and use pull requests to
`develop`. Release branches start at `develop`, target `main`, then reconcile
release-only commits into `develop`. Hotfixes start at `main` and reach both.
Never push implementation changes directly to `main` or `develop`. The only
initialization exception is publishing the identical, README-only root commit
to those two branches in a newly created repository.

Use Conventional Commits and `vYYYY.MM.N` Calendar Versioning. Do not create a
release until the macOS acceptance checklist is completed. Do not auto-merge.

Run `./tests/validate.sh` and `git diff --check` before committing. Changes to
bootstrap or deployment must include tests for failure preservation. Keep Python
compatible with 3.9+, shell wrappers compatible with Apple's Bash 3.2, and Zsh
files compatible with the system shell. Use English identifiers and comments.

Keep plan and verify read-only. Apply must use this checkout without fetching.
Never commit local JSON, credentials, backups, logs or machine identifiers.
Never overwrite unmanaged shell settings, follow destination symlinks during
deployment, weaken macOS security settings, or enable a daemon implicitly.
Do not add dependencies for UI or JSON parsing without explaining the tradeoff.
