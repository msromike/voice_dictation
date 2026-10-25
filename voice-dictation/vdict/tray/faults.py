"""The mic-fault and model-fault modals. Wired -- only app imports it, and app
registers these two into the console's dispatch so console never reaches here."""

import tkinter as tk
from collections.abc import Callable

from vdict.tray.const import MIC_FAULT_FLAG_PATH
from vdict.tray.dpi import scale

# Declared, deliberately unbound. A fault raised before install() should be a
# loud NameError, not a silently skipped modal.
_root: tk.Tk
_open_settings: Callable[[], tk.Toplevel]
_force_quit: Callable[[], None]
_set_fault_shown: Callable[[bool], None]


def install(root, open_settings, force_quit, set_fault_shown):
    """Hand in everything the modals reach for.
    open_settings returns the live Settings window, which a modal parents to."""
    global _root, _open_settings, _force_quit, _set_fault_shown
    _root, _open_settings = root, open_settings
    _force_quit, _set_fault_shown = force_quit, set_fault_shown


def _build_modal(title, text):
    """Shared shape for mic-fault/model-fault: raise the window, open Settings
    as signage underneath, an application-modal Toplevel naming the problem."""
    # Set before open_settings, not after -- the 100ms exit poll runs during it.
    _set_fault_shown(True)
    _root.deiconify()
    settings_win = _open_settings()

    modal = tk.Toplevel(settings_win)
    modal.title(title)
    modal.transient(settings_win)
    modal.grab_set()

    tk.Label(modal, text=text, wraplength=scale(360),
             justify="left", padx=scale(20),
             pady=scale(20)).pack()
    return modal


def show_mic_fault(text):
    """mic-fault's dispatch bundle -- Close writes the resume flag then force-quits."""
    modal = _build_modal("No Microphone Detected", text)

    def close():
        MIC_FAULT_FLAG_PATH.write_text(text)
        _force_quit()

    tk.Button(modal, text="Close", command=close).pack(
        pady=(0, scale(20)))
    modal.protocol("WM_DELETE_WINDOW", close)


def show_model_fault(text):
    """model-fault's dispatch bundle -- OK just closes the modal; Save
    (existing, unchanged) is the recovery."""
    modal = _build_modal("Model Load Failed", text)
    tk.Button(modal, text="OK", command=modal.destroy).pack(
        pady=(0, scale(20)))
    modal.protocol("WM_DELETE_WINDOW", modal.destroy)
