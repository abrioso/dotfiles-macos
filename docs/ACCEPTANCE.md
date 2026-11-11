# Mac acceptance before the first release

Record locally: the full commit under test, model/architecture, macOS version,
Python/Homebrew versions, selected groups/modules and each step's outcome.
Do not publish account names, email addresses, tokens, full logs or private settings.

- [ ] Confirm macOS 15+ and a native terminal; check Intel behavior if applicable.
- [ ] Review bootstrap, install prerequisites and confirm PATH in a new window.
- [ ] Test TUI arrows/Space, cancellation without new files and explicit saving.
- [ ] Enter Git identity only in local JSON; confirm `git status` ignores it.
- [ ] Back up profiles and settings before the first apply.
- [ ] Run text/JSON plans and confirm no changes, elevation or downloads.
- [ ] Apply the minimal selection in a test account; verify applications and the Zsh prompt.
- [ ] Repeat setup; identical files must not change or create new backups.
- [ ] Select the Nerd Font in the terminal and check prompt glyphs and path/Git segments.
- [ ] Test standalone PowerShell and the VS Code integrated terminal, if selected.
- [ ] Check `git config --global --includes --get user.name` and aliases without publishing the values.
- [ ] Simulate a marker/symlink conflict in a test account; setup must stop before installation.
- [ ] Run diagnostics with and without `--check-packages`; interpret the documented exit codes.
- [ ] Confirm Docker/Tailscale were not started/authenticated automatically.
- [ ] If using Colima, configure Compose and resources, start manually and test a disposable stack.
- [ ] If using Finder preferences, confirm values and test restoring one key.
- [ ] Test profile restoration from the manifest; preserve subsequent changes.
- [ ] Confirm updating the checkout does not alter deployed profiles or reset local JSON.
- [ ] Wait for all three CI platforms and PR review before merging into `develop`.

Physical Mac acceptance: **pending** at initial creation. No software installation
or preference changes have been performed on the user's Mac.
