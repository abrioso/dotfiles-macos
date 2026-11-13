"""Curses selector: edit in memory, save explicitly, cancel without writes."""
import copy
import curses

from .config import MODULES, ConfigError, validate

LABELS = {
    "shell": "Zsh and prompt (preserves existing configuration)",
    "git": "Git (personal values in local JSON)",
    "pwsh": "PowerShell profile (requires the pwsh group)",
    "macos": "Finder: file extensions, path bar and status bar",
}


def toggle(config, key, name):
    selection = config[key]
    if name in selection:
        selection.remove(name)
    else:
        if key == "package_groups" and name in ("colima", "docker-desktop"):
            other = "colima" if name == "docker-desktop" else "docker-desktop"
            if other in selection:
                selection.remove(other)
        selection.append(name)


def choose(config, catalog):
    draft = copy.deepcopy(config)
    rows = [("package_groups", name, catalog[name]["description"]) for name in catalog]
    rows += [("modules", name, LABELS[name]) for name in MODULES]

    def screen(stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        index = 0
        message = ""
        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            if height < 8 or width < 35:
                stdscr.addnstr(0, 0, "Enlarge the window; Q cancels.", max(1, width - 1))
                if stdscr.getch() in (ord("q"), ord("Q"), 27):
                    return None
                continue
            stdscr.addnstr(0, 0, "dotfiles-macos | Per-machine configuration", width - 1)
            stdscr.addnstr(1, 0, "↑/↓ move | Space toggle | S save | Q cancel", width - 1)
            visible = height - 5
            start = max(0, min(index - visible + 1, len(rows) - visible))
            for line, (key, name, description) in enumerate(rows[start:start + visible], 3):
                checked = "x" if name in draft[key] else " "
                text = "[" + checked + "] " + ("Module " if key == "modules" else "") + name + " — " + description
                style = curses.A_REVERSE if line - 3 + start == index else curses.A_NORMAL
                stdscr.addnstr(line, 0, text, width - 1, style)
            stdscr.addnstr(height - 1, 0, message, width - 1)
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                index = (index - 1) % len(rows)
            elif key in (curses.KEY_DOWN, ord("j")):
                index = (index + 1) % len(rows)
            elif key == ord(" "):
                toggle(draft, rows[index][0], rows[index][1])
                message = "Changes have not been saved yet."
            elif key in (ord("q"), ord("Q"), 27):
                return None
            elif key in (ord("s"), ord("S")):
                try:
                    validate(draft, catalog)
                except ConfigError as exc:
                    message = str(exc)
                else:
                    return draft

    return curses.wrapper(screen)
