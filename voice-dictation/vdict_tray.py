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
import winreg
from pathlib import Path

import win32api
import win32event

from vdict import __version__
from vdict.common import output
from vdict.tray.const import MB_ICONERROR, RAISE_EVENT_NAME

try:
    # Must run before any Tk root exists or any GetDpiForSystem call -- which
    # is why it stays here. Getting it wrong is blurry text, not an exception.
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Win32 GetLastError value returned when the single-instance mutex exists.
ERROR_ALREADY_EXISTS = 183
# AllowSetForegroundWindow's "any process" -- the running copy's PID is unknown here.
ASFW_ANY = -1

# Where an updater finds this copy. Per-user, so no admin. The one thing the app
# writes outside userdata/, because it has to be findable without knowing the folder.
REGISTRY_KEY = r"Software\VoiceDictation"
APP_DIR = Path(__file__).resolve().parent.parent


def _record_location():
    """Write this copy's folder and version. Every launch, so a moved folder is
    found again the first time it runs from its new place."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
        winreg.SetValueEx(key, "InstallDir", 0, winreg.REG_SZ, str(APP_DIR))
        winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, __version__)

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
            # Launched again: the running copy raises its window. Windows gave this
            # process the foreground for the launch; it is handed on before exit.
            ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
            win32event.SetEvent(win32event.CreateEvent(
                None, False, False, RAISE_EVENT_NAME))  # pyright: ignore[reportArgumentType]
            sys.exit(0)

        # After the mutex: a second launch from another folder must not claim the record.
        _record_location()

        # Imported here, after SetProcessDpiAwareness has run.
        from vdict.tray.app import App

        App().run()
    except Exception:
        _log_startup_crash()
        raise
