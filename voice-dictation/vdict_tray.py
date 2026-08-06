#!/usr/bin/env python3
"""Voice Dictation entry point. Its path is pinned by vdict_run.bat,
vdict_install.bat and startup_folder_install.bat -- it must stay here."""
import sys

# Must precede the imports below -- win32event raises ImportError elsewhere.
if sys.platform != "win32":
    sys.exit("Voice Dictation is Windows-only. See 'Windows only' in the "
             "README for what a port would involve -- one would be welcome.")

import ctypes
import traceback

import win32api
import win32event

from vdict.common import output
from vdict.tray.const import MB_ICONERROR

try:
    # Must run before any Tk root exists or any GetDpiForSystem call -- which
    # is why it stays here. Getting it wrong is blurry text, not an exception.
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Win32 GetLastError value returned when the single-instance mutex exists.
ERROR_ALREADY_EXISTS = 183

def _log_startup_crash():
    """Write an unhandled startup exception to the error log and show it on screen"""
    text = traceback.format_exc()
    summary = text.strip().splitlines()[-1]
    output.write_error_log("Startup crash", text)

    # Config has no fallbacks, so a malformed config.json lands here. There is
    # no console yet at this point, so the dialog is the only visible surface.
    try:
        ctypes.windll.user32.MessageBoxW(
            None,
            f"{summary}\n\nFull details were written to:\n{output.ERROR_LOG_PATH}\n\n"
            f"If this mentions config.json, delete that file and relaunch "
            f"to restore the default settings.",
            "Voice Dictation failed to start", MB_ICONERROR)
    except Exception:
        # Never let the error reporter mask the original traceback, which
        # the caller re-raises and the log above already captured.
        pass


if __name__ == "__main__":
    try:
        # Without an explicit AUMID, Windows taskbar groups this window under
        # pythonw.exe's identity and shows its icon instead of ours.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "VoiceDictation.Tray")

        # Single-instance check using Windows mutex.
        # NULL security attributes is the documented default; the stub omits it.
        mutex = win32event.CreateMutex(
            None, False, "VoiceDictationTrayMutex")  # pyright: ignore[reportArgumentType]
        if win32api.GetLastError() == ERROR_ALREADY_EXISTS:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                "Voice Dictation",
                "Voice Dictation is already running in your system tray.")
            sys.exit(1)

        # Imported here, after SetProcessDpiAwareness has run.
        from vdict.tray.app import App

        App().run()
    except Exception:
        _log_startup_crash()
        raise
