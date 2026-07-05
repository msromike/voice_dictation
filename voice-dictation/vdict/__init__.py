"""
Voice Dictation Library - Exportable STT components

This package provides reusable voice-to-text components for:
- Audio capture with PTT (push-to-talk)
- Whisper-based speech-to-text transcription
- Text injection at cursor position

Can be imported by RAVEN or other projects.
"""

from .audio import AudioCapture
from .stt import STTEngine
from .keyboard import KeyboardInjector, PTTListener

__version__ = "0.1.0"
__all__ = ["AudioCapture", "STTEngine", "KeyboardInjector", "PTTListener"]
