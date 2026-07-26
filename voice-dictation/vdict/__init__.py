"""
Voice Dictation - internal package for the vdict.py daemon.

Deliberately bare. Submodules are imported directly by their consumers
(from vdict.audio import AudioCapture), never re-exported here.

Do NOT re-add convenience re-exports. vdict_tray.py imports a single constant
from vdict.config, and anything imported in this file would be dragged into
the tray process along with it -- which for the former re-exports meant
sounddevice and faster-whisper, for the sake of one Path.
"""

__version__ = "1.0.0"
