"""The console output queue and the two report functions.
Leaf -- imports no vdict.tray module, so anything may import it."""

import queue

from vdict.common.output import write_error_log

# Produced from any thread, drained on the Tk timer.
output_queue = queue.Queue()

_screen = None


def install_screen(fn):
    """Register fn(context, text) as the screen half of error_log()."""
    global _screen
    _screen = fn


def log(category, text):
    """Put (category, text) on output_queue -- no wire format needed in-process."""
    output_queue.put((category, text))


def error_log(context, text, screen=True):
    """Write to the error log, then best-effort dump the same text onto the screen.
    screen=False where the caller already prints a sentence a human can act on."""
    write_error_log(context, text)
    if _screen is None or not screen:
        return
    try:
        _screen(context, text)
    except Exception:
        # A screen failure must never undo the disk write above it.
        pass
