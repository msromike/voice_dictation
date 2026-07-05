Voice Dictation Daemon
=======================

System-wide push-to-talk voice-to-text tool. Click middle mouse button,
speak, click again, and text appears at cursor. Local, no cloud, no tracking.

USAGE
-----

Run in console:
    python vdict.py

Output format:
    Voice Dictation READY
    Click MIDDLE MOUSE BUTTON to paste at cursor
    [0] Recording...
    [0] transcribed text here
    Stopped

Configuration:
    Edit config.json for audio device, model, PTT button


ARCHITECTURE
------------

vdict.py           - Main daemon entry point
config.json        - Configuration (audio device, model, PTT button)
vdict/
  audio.py         - Audio capture (sounddevice)
  stt.py           - Whisper speech-to-text (faster-whisper)
  keyboard.py      - PTT listener (pynput) & text injection (pyautogui/pyperclip)


DEPENDENCIES
------------

- faster-whisper   - STT engine
- sounddevice      - Audio capture
- numpy            - Audio data handling
- pynput           - PTT button detection
- pyautogui        - Keyboard simulation
- pyperclip        - Clipboard operations


CONFIGURATION
-------------

config.json structure:
    {
      "audio": {
        "device": "USB 2.0 Camera",  // Your microphone name
        "sample_rate": 16000
      },
      "stt": {
        "model": "base.en",  // tiny.en, base.en, small.en
        "device": "cpu"      // cpu or cuda
      },
      "ptt": {
        "button": "middle"   // middle or side
      }
    }

Find your audio device:
    python -c "import sounddevice as sd; print(sd.query_devices())"


INTEGRATION WITH RAVEN
----------------------

RAVEN can import STT components:

    from voice_dictation.vdict import STTEngine, AudioCapture
    
    stt = STTEngine(model_name="base.en", device="cpu")
    stt.load()
    text = stt.transcribe(audio_data)


DESIGN NOTES
------------

CPU vs GPU: Testing showed CPU is faster for short voice clips (1-3 seconds)
due to CUDA context swap overhead. GPU only wins for batch processing or
continuous streaming. Default: device="cpu"

PTT Trigger: Middle mouse button chosen to avoid conflicts with typing.
Toggle mode: Click to start recording, click to stop and transcribe.

Model Selection: base.en recommended for balance of speed (~200ms) and
accuracy (3-5% WER). tiny.en faster but less accurate, small.en more
accurate but slower.


STATUS
------

Fully functional. Tested on Windows 10/11 with USB headset microphone.
