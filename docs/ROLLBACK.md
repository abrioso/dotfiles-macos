# Rollback and removal

Each apply operation that changes files creates a private directory under
`~/.local/state/dotfiles-macos/backups/<timestamp>-<suffix>`. Its path is also
printed when a phase fails. Unchanged reruns do not create another backup.
Backups may contain personal data from existing profiles; do not publish them.

`manifest.json` records destinations, prior existence, backup copies and previous
permissions. Before restoring, close affected terminals and preserve changes made
since the apply operation. For each entry with `existed: true`, compare the `.bak`
file with its destination and copy the intended version. Restore the original
permissions recorded in `mode` (a decimal value). For entries with `existed: false`,
remove only the created file if it still has no personal changes and is no longer
needed. Do not delete entire directories.

To remove only the integration, remove blocks delimited by
`# >>> dotfiles-macos >>>` and `# <<< dotfiles-macos <<<` from `.zshrc`, `.zprofile`,
`.gitconfig` and/or `~/.config/powershell/profile.ps1`. Preserve all other content.
Remove the Git include before deleting the managed `gitconfig` file. Copies
under `~/.config/dotfiles-macos` can then be reviewed and removed individually.

When present, `macos-preferences.json` records each changed preference's previous
value. For a key that did not exist, use `defaults delete <domain> <key>`;
for an existing key, use `defaults write <domain> <key> -bool true|false`
with its previous value. Run these commands only for recorded keys and after
comparing their current state. Logging out may be necessary to reflect the result.

There is no automatic global rollback because it could erase later changes.
Restoring files does not remove Homebrew packages or application data.
Review each uninstall individually. Do not use `brew bundle cleanup` for this
purpose; the catalog covers only part of the software installed on the machine.
