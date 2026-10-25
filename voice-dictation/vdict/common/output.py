"""Shared output-category vocabulary: color, marker, box, and toast-eligibility per category.
Also the error log's disk-write, since daemon and tray both need to reach it."""

import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

def divider_line():
    """The dashed, timestamped line that closes a session block. Dashes, not the
    header's equals signs -- it divides sections, it does not open the log."""
    return f" {datetime.now():%Y-%m-%d %H:%M:%S} ".center(60, "-")


# Created at import so the log is writable before anything can fail.
LOG_DIR = Path(__file__).parent.parent.parent.parent / "userdata" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG_PATH = LOG_DIR / "tray_error.log"


class CategorySpec(NamedTuple):
    color: str    # "dim", "yellow", "red", or "none"
    marker: str   # "REC", "DONE", "NOTE", "ERROR", or "" for no marker
    box: bool = False
    toast: bool = False


CATEGORIES: dict[str, CategorySpec] = {
    "header":     CategorySpec("dim", ""),
    "block":      CategorySpec("dim", ""),
    "rec":        CategorySpec("dim", "REC"),
    "done":       CategorySpec("dim", "DONE"),
    "note":       CategorySpec("yellow", "NOTE"),
    "error":      CategorySpec("red", "ERROR"),
    "transcript": CategorySpec("none", ""),
    "ready":      CategorySpec("dim", "", toast=True),
    "download":   CategorySpec("dim", "", toast=True),
    "loading":    CategorySpec("dim", ""),
    "mic-fault":   CategorySpec("red", "ERROR", box=True),
    "model-fault": CategorySpec("red", "ERROR", box=True),
}


# The daemon logs from three threads (capture, clipboard, pipe reader). print() is
# two writes, so without this a "ready" line once landed inside a note.
_stdout_lock = threading.Lock()


def log(category, text):
    """Emit one "category|text" line to stdout -- the daemon-to-tray wire format."""
    had_newline = "\n" in text
    if had_newline:
        text = text.replace("\n", " ")
    with _stdout_lock:
        sys.stdout.write(f"{category}|{text}\n")
        sys.stdout.flush()
    if had_newline:
        log("note", "Unexpected line break detected and removed from the "
                     "output -- if this keeps happening, it's worth a bug report.")


def parse(line):
    """Split one "category|text" line into (category, text). No "|" -> (None, line)."""
    category, sep, text = line.partition("|")
    if not sep:
        return None, category
    return category, text


def write_error_log(context, text):
    """Append one pre-formatted entry to the error log. Disk-write only, no screen."""
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write(f"{context}\n{text}")
