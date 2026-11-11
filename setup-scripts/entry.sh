#!/bin/bash
# Compatible with macOS Bash 3.2. Do not install anything from a normal entry point.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
    echo 'Python 3.9+ is required. Run ./setup-scripts/bootstrap.sh first.' >&2
    exit 2
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 2)' || {
    echo 'Python 3.9+ is required.' >&2
    exit 2
}
exec python3 -B "$script_dir/dotfiles.py" "$@"
