"""Atomic independent copies, marked blocks and per-run backup manifests."""
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .config import ConfigError

BEGIN = "# >>> dotfiles-macos >>>"
END = "# <<< dotfiles-macos <<<"


def assert_safe(path):
    path = Path(path)
    for candidate in (path,) + tuple(path.parents):
        if candidate.is_symlink():
            raise ConfigError("Symlink destination refused: " + str(candidate))
    if path.exists() and not path.is_file():
        raise ConfigError("Destination is not a regular file: " + str(path))


def existing_text(path):
    assert_safe(path)
    try:
        return Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    except (OSError, UnicodeError) as exc:
        raise ConfigError("Cannot read UTF-8 destination: " + str(path)) from exc


def marked_text(existing, body):
    block = BEGIN + "\n" + body.rstrip("\n") + "\n" + END
    if BEGIN in existing or END in existing:
        if existing.count(BEGIN) != 1 or existing.count(END) != 1:
            raise ConfigError("Duplicate/incomplete managed markers; review the file manually.")
        start = existing.index(BEGIN)
        finish = existing.index(END) + len(END)
        if start >= finish or (start and existing[start - 1] != "\n"):
            raise ConfigError("Invalid managed block boundaries.")
        if finish < len(existing) and existing[finish] != "\n":
            raise ConfigError("Invalid managed block suffix.")
        return existing[:start] + block + existing[finish:]
    return existing + ("\n" if existing and not existing.endswith("\n") else "") + block + "\n"


def atomic_write(path, data, mode=0o600):
    path = Path(path)
    assert_safe(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".dotfiles-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Deployment:
    def __init__(self, home):
        self.home = Path(home)
        self.backup_dir = None
        self.entries = []

    def _manifest(self):
        atomic_write(self.backup_dir / "manifest.json",
                     json.dumps(self.entries, indent=2).encode() + b"\n")

    def _start(self):
        if self.backup_dir is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
            self.backup_dir = self.home / ".local/state/dotfiles-macos/backups" / stamp
            assert_safe(self.backup_dir / "manifest.json")
            self.backup_dir.mkdir(mode=0o700, parents=True)

    def write(self, path, text):
        path = Path(path)
        assert_safe(path)
        data = text.encode("utf-8")
        old = path.read_bytes() if path.exists() else None
        if old == data and path.stat().st_nlink == 1:
            return False
        self._start()
        entry = {"path": str(path), "existed": old is not None}
        if old is not None:
            backup = self.backup_dir / (str(len(self.entries)) + ".bak")
            atomic_write(backup, old)
            entry.update(backup=backup.name, mode=stat.S_IMODE(path.stat().st_mode))
        self.entries.append(entry)
        self._manifest()  # Persist rollback information before changing the destination.
        atomic_write(path, data)
        return True

    def record_preferences(self, values):
        self._start()
        atomic_write(self.backup_dir / "macos-preferences.json",
                     json.dumps(values, indent=2).encode() + b"\n")
