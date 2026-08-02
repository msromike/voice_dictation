# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A double beep when the speech engine finishes loading, so you know it is ready
  without watching the output window. It also sounds after Save & Restart.

- A timestamp centered in the divider line under READY, so a restart's start
  time is visible at a glance when scanning back through the output window.

- A hotkey that raises the output window from any application. Bind it in
  Settings under "Output Window Hotkey". Nothing is bound out of the box --
  any combination shipped as a default would collide on somebody's machine and
  look broken on first launch. Binding a key with no modifier is allowed, but
  warns first, because that key stops doing whatever it normally did.

- An application icon. The Desktop shortcut, the Startup shortcut, and the
  system tray now share one icon instead of showing the generic batch-file cog,
  the Python logo, and a shape drawn at runtime. The output window's title bar
  and Alt+Tab preview use it too. The Windows 11 taskbar button itself still
  shows the Python icon while running as a script -- that one reads the icon
  baked into pythonw.exe, which no in-process call can override; only
  compiling to a real .exe changes it.

- A distinct tone when a recording is too short to transcribe (under 0.4
  seconds), so you know immediately rather than waiting for text that never
  comes. The console explains why: "Not transcribed -- hold the button at
  least 0.4s."

- A clear error when the AI model fails to load, instead of a crash. A popup
  and the output window name the model and the actual error; Settings stays
  open underneath so you can pick a different model and Save & Restart
  without relaunching the app.

### Changed

- Enable Audio Beeps now silences only the start and stop tones. The double beep
  keeps sounding, because it reports the engine coming up or a toggle recording
  abandoned after two minutes -- both worth knowing whether or not you want a
  beep on every dictation.

- A broken config.json now resets only the affected setting, not the whole
  file. The output window names exactly what changed and what it reset to,
  for example "Push-to-talk mode - HOLD" -- everything else you configured is
  left alone. A file that cannot be parsed at all still resets in full, since
  there is nothing left to preserve in that case.

- The missing-microphone message now names the specific microphone Voice
  Dictation was configured to use, or says so plainly if none was set. Seeing
  "no microphone detected" for a device you can see is plugged in reads as a
  broken app; naming it makes clear which one to reconnect.

- The failed-to-load-model message now says what to do about it -- pick a
  different model or switch to CPU in Settings, then Save & Restart --
  instead of just naming the underlying error.

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

- A missing microphone now closes the app entirely instead of leaving it in a
  half-working state -- an error box with Settings open behind it, but the
  speech engine already dead. Reconnect the device or pick a different one,
  then relaunch: Settings reopens automatically with an explanation of what
  happened, no need to hunt for it.

- An unexpected error in the app's own interface now shows a plain system
  dialog and closes the whole app, instead of a notification toast that left
  it running in a possibly broken state. A crash during startup shows the
  same kind of dialog. Both work even when the failure is inside the app's
  own display code, which a toast or a styled dialog could not guarantee.

### Fixed

- Settings no longer stays pinned above every other window for as long as
  it's open. It still pops to the front the moment it appears, but releases
  that afterward, so switching to another app no longer leaves it floating
  on top.

- A push-to-talk rebind failure's entry in the error log now contains a real
  traceback. It previously recorded nothing useful, because the error detail
  was gone by the time it got written down.

- Binding push-to-talk to a mouse button that fails to register no longer
  crashes silently in the background. It's now reported the same way a
  keyboard-side failure already was.

- Exit no longer gets stuck. Previously, if any step of shutting down failed --
  saving the console's state, stopping the daemon, or removing the tray icon --
  clicking Exit would do nothing, with no explanation. Each step now runs
  independently, so one failure cannot block the others or the app closing. A
  failure still shows a dialog naming the problem, with details in the output
  window and the error log, before exiting anyway.

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

- The daemon no longer crashes with a raw traceback if the microphone
  disconnects mid-session, after a recording has already started
  successfully. It now shows the same "Configured microphone not found"
  message already used when the microphone can't be found at launch, and the
  tray still opens Settings so you can pick another device or reconnect and
  Save & Restart.

- The daemon no longer crashes when a transcription contains a character
  outside the Windows ANSI codepage -- curly quotes, em-dashes, and accented
  characters are common in Whisper's output. Both processes now communicate
  over UTF-8 explicitly instead of falling back to the system default.

- The installer's Desktop shortcut no longer points at a batch file. It now
  launches the venv's `pythonw.exe` directly with the tray script as an
  argument, the same way the Startup-folder shortcut already did -- avoids a
  console window briefly flashing on launch. Batch files were also renamed
  for clarity (`setup.bat` to `vdict_install.bat`, `run.bat` to
  `vdict_run.bat`, `install_startup.bat`/`uninstall_startup.bat` to
  `startup_folder_install.bat`/`startup_folder_uninstall.bat`), with every
  reference across the app and README updated to match.

- Settings and the output window no longer snap to the default corner when
  reopened near a screen edge. The saved position is now nudged just inside
  the visible desktop instead of being discarded outright.

- The About dialog now says "Whisper" instead of "speech to text" -- matches
  the terminology already used everywhere else in the app (Settings already
  said "Whisper model").

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
