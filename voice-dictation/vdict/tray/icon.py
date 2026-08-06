"""The pystray system-tray icon. Wired -- only app imports it, and its three
menu items arrive as callables."""

import ctypes

import pystray
from PIL.IcoImagePlugin import IcoImageFile

from vdict.tray.const import ICON_PATH

# GetSystemMetrics index for the tray/small-icon edge length. One consumer,
# so it lives here rather than in const.py.
SM_CXSMICON = 49


def create(show_window, open_settings, exit_app):
    """Create system tray icon from the shared .ico"""
    wanted = ctypes.windll.user32.GetSystemMetrics(SM_CXSMICON)
    with ICON_PATH.open("rb") as handle:
        icon = IcoImageFile(handle)
        # The .ico holds 16/32/48/256. Assigning .size selects a stored frame
        # rather than letting Windows rescale whichever one it opened.
        icon.size = min(icon.ico.sizes(), key=lambda s: abs(s[0] - wanted))
        img = icon.convert("RGBA")

    menu = pystray.Menu(
        pystray.MenuItem("Show Output", show_window, default=True),
        pystray.MenuItem("Settings...", open_settings),
        pystray.MenuItem("Exit", exit_app)
    )

    return pystray.Icon("voice_dictation", img, "Voice Dictation", menu)
