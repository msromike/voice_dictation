"""Headless check of the category dispatch table and daemon-side wire format. No app launch."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "voice-dictation"))

from vdict.common import output  # noqa: E402 -- needs the path insert above first

EXPECTED_CATEGORIES = (
    "header", "block", "rec", "done", "note",
    "error", "transcript", "ready", "download", "loading",
    "mic-fault", "model-fault")


def check_categories():
    """Print color/marker/box/toast per category -- KeyError if any is missing."""
    for name in EXPECTED_CATEGORIES:
        spec = output.CATEGORIES[name]
        print(f"{name}: color={spec.color} marker={spec.marker!r} "
              f"box={spec.box} toast={spec.toast}")


def check_newline_handling():
    """Confirm log() strips an embedded newline and self-announces via a note line."""
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        output.log("note", "line one\nline two")
    for line in buf.getvalue().splitlines():
        print(repr(line))


if __name__ == "__main__":
    check_categories()
    check_newline_handling()
