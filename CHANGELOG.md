# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A hotkey that raises the output window from any application. Bind it in
  Settings under "Output Window Hotkey". Nothing is bound out of the box --
  any combination shipped as a default would collide on somebody's machine and
  look broken on first launch. Binding a key with no modifier is allowed, but
  warns first, because that key stops doing whatever it normally did.

- An application icon. The Desktop shortcut, the Startup shortcut, and the
  system tray now share one icon instead of showing the generic batch-file cog,
  the Python logo, and a shape drawn at runtime.

### Changed

- The output window opens with a header naming the push-to-talk mode and
  trigger, the hotkey, the compute device, and the model. The model line
  carries its real size on disk, which is what tells you a large model will not
  fit in your GPU; it reads bare until that model has been downloaded.

- Save & Restart no longer reprints the welcome banner, which made the log look
  as though it had been wiped. It reprints the header instead, so a changed
  model or compute device shows up in the log rather than being taken on trust.

- The window that shows dictation activity is now called the output window
  throughout. The Settings checkbox reads "Show Output on Startup", previously
  "Show Console on Startup".

### Fixed

- The push-to-talk picker no longer locks up. A key it could not read left the
  button greyed out for the rest of the session, with a global mouse hook still
  running behind it and nothing said. It now restores the previous binding and
  reports the failure.

- Escape cancels the push-to-talk picker instead of binding itself.

- Clicking anywhere while the push-to-talk picker is waiting -- including on the
  Settings close button -- no longer raises a "cannot bind that button" warning.
  Unsupported buttons are ignored and the picker keeps waiting.

- The push-to-talk picker no longer accepts the left mouse button. Binding it
  made every click start a recording.

- `setup.bat` now resolves paths from its own folder. Running it from a
  different working directory previously created the Desktop shortcut with the
  wrong target.

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
- Windows only. Launching on another platform exits with an explanation rather
  than a traceback. See "Windows only, for now" in the README for what a port
  would involve.
