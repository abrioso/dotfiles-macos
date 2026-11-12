"""Opt-in progress on stderr; never dump configuration or command output."""
import sys

enabled = False


def progress(message):
    if enabled:
        print("[verbose] " + message, file=sys.stderr, flush=True)
