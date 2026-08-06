"""Raw transcript text to its own rotating file. Leaf -- no Tk, no vdict.tray
import. The console calls write(); nothing reads this file back."""

import logging
import logging.handlers

from vdict.common.output import LOG_DIR

# B14 groundwork -- gated on a flag, not a Settings checkbox yet.
ENABLED = True
PATH = LOG_DIR / "transcript_log.txt"

_logger = logging.getLogger("vdict.transcript")
_logger.propagate = False
_logger.setLevel(logging.INFO)
_handler = logging.handlers.RotatingFileHandler(
    PATH, maxBytes=100 * 1024 * 1024, backupCount=5,
    encoding="utf-8", delay=True)
_handler.setFormatter(logging.Formatter("%(message)s"))
_logger.addHandler(_handler)


def write(text):
    """Append one raw-text line to transcript_log.txt -- no timestamp, no level."""
    _logger.info(text)
