"""Window geometry persistence. Leaf -- imports no vdict.tray module.
One door per window: manage() restores then tracks, save_all() flushes."""

import re

from vdict.common.config import Pos

# What a tracked field stores: the whole "WxH+X+Y" string, or just a Pos(x, y).
GEOMETRY, POS = "geometry", "pos"

# Marks a GEOMETRY string whose window was maximized. The geometry after it is
# the pre-maximize one, which is what un-maximizing has to return to.
ZOOM_PREFIX = "zoomed "

# config.ui field name -> {shape, geometry, zoomed, alive}
_tracked = {}

_flush = None


def set_flush(fn):
    """Register the save a destroyed window triggers. Without it a transient
    window's position reaches disk only at the next hide or exit."""
    global _flush
    _flush = fn


def _geometry_parts(geometry):
    """Split a Tk geometry string "WxH+X+Y" into (width, height, x, y).
    Returns None before a window is placed, when Tk emits no origin."""
    match = re.match(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)', geometry)
    if not match:
        return None
    return tuple(int(g) for g in match.groups())


def _clamp_to_desktop(win, x, y, width, height):
    """Clamp (x, y) so a width x height window stays inside the desktop spanning
    every attached monitor. Same algorithm as tk.tcl's ::tk::PlaceWindow."""
    vx, vy = win.winfo_vrootx(), win.winfo_vrooty()
    vw, vh = win.winfo_vrootwidth(), win.winfo_vrootheight()
    x = max(vx, min(x, vx + vw - width))
    y = max(vy, min(y, vy + vh - height))
    return x, y


def _restore(window, config, field, shape, entry):
    """Place window at what config.ui.<field> holds. False when it holds
    nothing usable, leaving the window wherever its caller put it."""
    saved = getattr(config.ui, field)
    if not saved:
        return False

    if shape == POS:
        width, height = window.winfo_reqwidth(), window.winfo_reqheight()
        x, y = _clamp_to_desktop(window, saved.x, saved.y, width, height)
        window.geometry(f"+{x}+{y}")
        return True

    zoomed = saved.startswith(ZOOM_PREFIX)
    parts = _geometry_parts(saved[len(ZOOM_PREFIX):] if zoomed else saved)
    if parts is None:
        return False
    width, height, x, y = parts
    x, y = _clamp_to_desktop(window, x, y, width, height)
    window.geometry(f"{width}x{height}+{x}+{y}")
    if zoomed:
        # Windows records its own restore rectangle. Without settling the
        # geometry first, un-maximizing lands wherever the window was mapped.
        window.update_idletasks()
        # Windows-only state; X11 raises. vdict_tray.py's platform guard is
        # what makes that safe to ignore here.
        window.state("zoomed")
        entry["zoomed"] = True
    return True


def manage(window, config, field, shape):
    """Restore config.ui.<field> onto window, then cache every move and resize.
    False means nothing was saved, so the caller does its own placement."""
    entry = {"shape": shape, "geometry": None, "zoomed": False, "alive": True}
    _tracked[field] = entry

    def remember(event):
        if not entry["alive"] or event.widget is not window:
            return
        state = window.state()
        if state == "zoomed":
            # Keep the pre-maximize geometry: Tk reports only the zoomed one.
            entry["zoomed"] = True
        elif state == "normal":
            entry["zoomed"] = False
            entry["geometry"] = window.geometry()

    def gone(event):
        # Reads no geometry -- the cache already holds the last valid value.
        # Flushes, because a reopened window restores from disk, not the cache.
        if event.widget is window:
            entry["alive"] = False
            if _flush is not None:
                _flush()

    window.bind("<Configure>", remember, add="+")
    window.bind("<Destroy>", gone, add="+")
    return _restore(window, config, field, shape, entry)


def save_all(config):
    """Write every cached geometry onto config.ui, converting per field.
    A cache that will not parse leaves its field alone, never writing None."""
    for field, entry in _tracked.items():
        parts = _geometry_parts(entry["geometry"] or "")
        if parts is None:
            continue
        if entry["shape"] == POS:
            setattr(config.ui, field, Pos(x=parts[2], y=parts[3]))
        else:
            geometry = entry["geometry"]
            setattr(config.ui, field,
                    ZOOM_PREFIX + geometry if entry["zoomed"] else geometry)
