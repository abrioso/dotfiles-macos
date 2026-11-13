# Contributing

Start from `develop`, create a `feature/*` or `fix/*` branch, and open a pull request
to `develop`. Use Conventional Commits. See [Gitflow](docs/GITFLOW.md).

Run `./tests/validate.sh` before committing. Keep Bash compatible with 3.2 and
Python compatible with 3.9+. Validate new package tokens against the official
Homebrew API. Keep package order when it encodes dependencies. Add regression
tests for changed provisioning behaviour and failure cases; never apply the
configuration to a shared CI host as a test.

Shared defaults belong in `*.json.example`; machine choices belong in ignored
JSON. Preserve the read-only contract for plan/verify, independent deployed
copies, explicit updates, safe reruns and the separation from service startup.
Update the acceptance checklist for new platform assumptions.
