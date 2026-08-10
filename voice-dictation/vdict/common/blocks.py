"""Paragraph blocks: which dictations belong to the same message.
A block opens on the first dictation into a window and closes on a plain Enter there."""

import threading
import time


class BlockTracker:
    """Maps a window handle to the block currently open in it.
    Read from the capture loop, written from the keyboard listener's thread."""

    def __init__(self):
        """Start with no blocks open."""
        self._lock = threading.Lock()
        self._blocks = {}

    def block_for(self, hwnd, pid):
        """Return the block id open in hwnd, opening one if none is.
        A different pid on the same handle means Windows reused it -- new block."""
        with self._lock:
            existing = self._blocks.get(hwnd)
            if existing is not None and existing[1] == pid:
                return existing[0]
            block_id = time.time_ns()
            self._blocks[hwnd] = (block_id, pid)
            return block_id

    def close(self, hwnd):
        """End the block open in hwnd. A handle holding no block is ignored."""
        with self._lock:
            self._blocks.pop(hwnd, None)
