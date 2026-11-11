# Security

Do not commit credentials, private configuration, backups or diagnostic exports.
Review changes to bootstrap downloads, package catalogs and profile execution.
The Homebrew installer is pinned to a commit and verified by SHA-256 before
execution; changing the pin requires reviewing the official installer and hash.
Installed Homebrew packages use Homebrew's integrity mechanisms and are not
version-pinned by this repository.

Plan/verify must not install, update, elevate or mutate configuration. Apply
must reject root/Rosetta execution and unsafe profile destinations. Do not disable
Gatekeeper, SIP, FileVault, the firewall or certificate validation to make a test pass.
Private local files are not a secrets vault; use Keychain or provider-supported
credential stores. Report suspected vulnerabilities privately to the repository
owner; do not publish tokens or personal configuration in an issue.
