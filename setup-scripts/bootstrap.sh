#!/bin/bash
# Reviewed official Homebrew installer, pinned by commit and SHA-256.
set -euo pipefail
install_homebrew=false
case "${1:-}" in
    '') ;;
    --install-homebrew) install_homebrew=true; shift ;;
    --help|-h)
        echo 'Usage: bootstrap.sh [--install-homebrew]'
        echo 'Prepares Homebrew/Python only. Does not apply dotfiles or start services.'
        exit 0 ;;
    *) echo 'Unknown option. Use --help.' >&2; exit 2 ;;
esac
if [ "$#" -ne 0 ]; then echo 'Unexpected arguments.' >&2; exit 2; fi
if [ "$(uname -s)" != Darwin ]; then echo 'macOS is required.' >&2; exit 2; fi
if [ "$(id -u)" -eq 0 ]; then echo 'Run without sudo.' >&2; exit 2; fi
macos_version="$(sw_vers -productVersion)"
if [ "${macos_version%%.*}" -lt 15 ]; then
    echo 'This baseline requires macOS 15 or newer.' >&2; exit 2
fi
if [ "$(/usr/sbin/sysctl -in sysctl.proc_translated 2>/dev/null || true)" = 1 ]; then
    echo 'Open a native terminal without Rosetta.' >&2; exit 2
fi
case "$(uname -m)" in
    arm64) brew_prefix=/opt/homebrew ;;
    x86_64) brew_prefix=/usr/local; echo 'Intel is a legacy Homebrew target; package support may vary.' ;;
    *) echo 'Unsupported architecture.' >&2; exit 2 ;;
esac
if ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
    echo 'Install Apple Command Line Tools: xcode-select --install'
    echo 'Complete the Apple installer, then rerun this script.'
    exit 2
fi
brew_bin="$brew_prefix/bin/brew"
if [ ! -x "$brew_bin" ]; then
    if [ "$install_homebrew" != true ]; then
        echo 'Homebrew is missing. Review this script, then run:'
        echo './setup-scripts/bootstrap.sh --install-homebrew'
        exit 2
    fi
    temporary_dir="$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-homebrew.XXXXXX")"
    trap 'rm -rf "$temporary_dir"' EXIT
    installer_commit=7986efac25016e41eed7e471666140c06f9d97cf
    installer_sha256=5f333bbe53bc490e51e7ccb1df8779b3dd6ee73a1a7379efda216edb08ccb148
    /usr/bin/curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
        "https://raw.githubusercontent.com/Homebrew/install/$installer_commit/install.sh" \
        -o "$temporary_dir/install.sh"
    actual_sha256="$(/usr/bin/shasum -a 256 "$temporary_dir/install.sh")"
    actual_sha256="${actual_sha256%% *}"
    if [ "$actual_sha256" != "$installer_sha256" ]; then
        echo 'Installer checksum mismatch; nothing executed.' >&2; exit 2
    fi
    /bin/bash "$temporary_dir/install.sh"
fi
if [ "$("$brew_bin" --prefix)" != "$brew_prefix" ]; then
    echo 'Homebrew prefix mismatch.' >&2; exit 2
fi
export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_ANALYTICS=1
# No eval of externally supplied configuration. Use the known native prefix.
export PATH="$brew_prefix/bin:$brew_prefix/sbin:$PATH"
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 2)'; then
    "$brew_bin" install python@3.13
    export PATH="$brew_prefix/opt/python@3.13/libexec/bin:$PATH"
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 2)'
echo 'Prerequisites ready. For this terminal, set the PATH if needed:'
# Preserve a literal $PATH for the user's parent shell.
# shellcheck disable=SC2016
printf 'export PATH="%s/opt/python@3.13/libexec/bin:%s/bin:%s/sbin:$PATH"\n' "$brew_prefix" "$brew_prefix" "$brew_prefix"
echo 'Next: ./setup-scripts/configure.sh; ./setup-scripts/setup.sh --plan'
