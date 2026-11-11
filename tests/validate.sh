#!/bin/bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B - <<'PY'
import ast
import json
from pathlib import Path
for path in list(Path('setup-scripts').rglob('*.py')) + list(Path('tests').glob('*.py')):
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=(3, 9))
for path in list(Path('dotfiles-configurations').glob('*.example')) + list(Path('themes').glob('*.json')):
    json.loads(path.read_text(encoding='utf-8'))
PY
for script in setup-scripts/*.sh tests/*.sh; do /bin/bash -n "$script"; done
for script in git-hooks/*; do /bin/sh -n "$script"; done
zsh -n shell/zshrc
zsh -n shell/zprofile
if command -v shellcheck >/dev/null 2>&1; then
    shellcheck setup-scripts/*.sh tests/*.sh git-hooks/*
else
    echo 'ShellCheck not installed; CI must run it before merge.'
fi
git diff --check
git diff --cached --check
