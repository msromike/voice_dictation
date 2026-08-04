"""Display scaling for pixel dimensions. Leaf -- imports nothing from vdict.tray."""

import ctypes

# Lazy, never computed at import: must not run before the entry module's
# SetProcessDpiAwareness call.
_scale = None


def _factor():
    """System DPI as a multiplier of 96, read once. 1.0 when Windows will not say."""
    global _scale
    if _scale is None:
        try:
            _scale = ctypes.windll.user32.GetDpiForSystem() / 96.0
        except Exception:
            _scale = 1.0
    return _scale


def scale(px):
    """Scale a pixel dimension for the current display.
    Never for font sizes -- Tk already scales point sizes by DPI on its own."""
    return int(px * _factor())
