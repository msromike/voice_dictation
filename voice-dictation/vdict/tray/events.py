"""Every yellow note and red error to its own rotating file, timestamped. Leaf -- no Tk,
no vdict.tray import. The console calls write(); the yellow lines otherwise die with it."""

import logging
import logging.handlers

from vdict.common.output import LOG_DIR

PATH = LOG_DIR / "event_log.txt"

# What a user would want to find later. Never transcripts or clipboard contents.
CATEGORIES = frozenset({"note", "error", "mic-fault", "model-fault"})

_logger = logging.getLogger("vdict.events")
_logger.propagate = False
_logger.setLevel(logging.INFO)
_handler = logging.handlers.TimedRotatingFileHandler(
    PATH, when="midnight", backupCount=30,
    encoding="utf-8", delay=True)
_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
_logger.addHandler(_handler)


def write(marker, text):
    """Append one "date time [MARKER] text" line to event_log.txt."""
    _logger.info(f"[{marker}] {text}")
