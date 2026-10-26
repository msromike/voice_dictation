"""Paths and constants with consumers in more than one tray module.
Leaf -- imports no vdict.tray module."""

from pathlib import Path

# The installed app's folder. FOUR .parent steps from vdict/tray/ -- three lands in
# voice-dictation/. A wrong MIC_FAULT_FLAG_PATH fails silently, not loudly.
INSTALL_DIR = Path(__file__).parent.parent.parent.parent

# Shared by the tray, the Desktop shortcut and the Startup shortcut.
ICON_PATH = INSTALL_DIR / "images" / "vdict.ico"

MIC_FAULT_FLAG_PATH = INSTALL_DIR / "userdata" / "mic_fault.flag"

# Single source for the project URL -- it appears in the console banner, the
# About box, and the Help menu.
PROJECT_URL = "https://github.com/msromike/voice_dictation"

# Named event a second launch sets so the running copy raises its window.
RAISE_EVENT_NAME = "VoiceDictationRaiseEvent"

# MessageBoxW icon flag, used where Tk itself could be the thing that's broken.
MB_ICONERROR = 0x10
