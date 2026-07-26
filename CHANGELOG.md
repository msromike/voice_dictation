# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-25

First public release.

### Added

- Push-to-talk voice dictation for Windows. Hold a button, speak, and the text
  is typed into whatever window has focus. Transcription runs locally through
  faster-whisper -- no account, no API key, and no audio leaves the machine.
- Configurable push-to-talk trigger. Any keyboard key or mouse button, bound by
  pressing it rather than typing a name.
- Hold and toggle recording modes. Toggle stops itself after two minutes so a
  forgotten recording cannot run indefinitely.
- System tray application with a live console window and a settings dialog.
- Menu bar on the console window (File, Edit, View, Help) with standard
  keyboard shortcuts.
- Save the console log to a text file.
- Adjustable console text size via Ctrl+scroll, Ctrl+plus, Ctrl+minus, and
  Ctrl+0. Window size, position, and text size persist between runs.
- File > Vocabulary opens `vocabulary.txt` in the default text editor.
- Help > Error Log opens `logs\tray_error.log`, greyed out when no errors have
  been recorded.
- Microphone selection, or the system default.
- Model selection from tiny.en through large-v3, and a CPU/GPU choice. The GPU
  option is offered only when a CUDA device is detected.
- Optional start and stop tones, so you can confirm the button registered
  without watching the screen.
- `vocabulary.txt` for names, acronyms, and jargon the recognizer gets wrong.
  Ships empty, since unused entries can appear in transcripts where they were
  not spoken.
- `setup.bat`, which creates an isolated virtual environment and installs the
  NVIDIA CUDA libraries through pip, so no separate CUDA toolkit install is
  needed.
- Optional launch on login, added by `setup.bat` and removable with
  `uninstall_startup.bat`.
- Windows notifications while the speech model downloads on first use.

### Notes

- Transcribed text is delivered through the clipboard, so whatever was
  previously copied is replaced on each dictation. See "Known limitations" in
  the README.
- Text cannot be typed into programs running as administrator unless this app
  is also run as administrator. This is a Windows restriction.
