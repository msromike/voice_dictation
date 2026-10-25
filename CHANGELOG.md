# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Installing from a USB stick, with no internet on the other computer.
  `create_usb_stick.bat` copies Python, the exact package versions you run,
  your downloaded speech models and the app -- and none of your settings,
  history or word list. `install.bat` on the stick installs, or updates, into
  your user's AppData with its own private Python, so it never clashes with
  another Python on that machine. See "Installing from a USB stick" in the
  README.

- Help > Event Log. Every yellow note and red error in the output window is
  also written to a file with the date and time, so a warning that scrolled
  past while you were working is still there later. It never holds your
  dictated text or anything you copied. One file per day, kept 30 days.

- A hotkey that pastes your last dictation again, wherever you are typing.
  For the dictation that landed nowhere -- no text field had focus -- or in
  the wrong window: click where you meant it to go and press the hotkey,
  instead of copying it out of the output window. Bind it in Settings under
  "Paste Last Dictation Hotkey"; nothing is bound out of the box.

- A mouse button can press Enter, so a dictation can be sent without
  reaching for the keyboard. Bind it in Settings under "Mouse Button for
  Enter"; nothing is bound out of the box. If you press it while a
  dictation is still being typed, the Enter waits until the text has landed,
  so a message never goes out without it.

- Launching the app while it is already running brings the output window to
  the front, instead of a box saying it is already running.

- A double beep when the speech engine finishes loading, so you know it is ready
  without watching the output window. It also sounds after a Save that changes
  the model, since that reloads the engine.

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
  open underneath so you can pick a different model and Save without
  relaunching the app.

- A capture history, for development builds only. With the development
  recording flag on, every press of the button writes one row to
  `userdata/dictation_history_PRIVATE.db`: when the audio started and ended,
  when the text landed, the recording's file, the model and compute type that
  ran, the transcript, how it ended (transcribed, too short, no speech, error,
  or abandoned after two minutes in toggle mode), the window it was aimed at,
  and a paragraph number shared by dictations into the same message until
  Enter is pressed. Failed captures get a row too. Without the flag nothing is
  written.

### Changed

- The beeps on/off checkbox is replaced by two volume sliders, 0 to 100:
  one for the high start beep, one for the low stop, ready and alert beeps.
  Laptop speakers make the high beep far louder than the low one, so each
  gets its own level, and beeps no longer force you to change the Windows
  volume. Turning both to 0 silences every tone, the ready and timeout double
  beeps included; the output window still reports the engine coming up and a
  toggle recording abandoned after two minutes, so nothing is lost. If you had
  beeps switched off, both sliders start at 0; otherwise both start at 50.

- Saving Settings no longer reloads the speech engine unless you changed the
  model or the compute device. A new button, microphone, mode, beep setting
  or vocabulary takes effect at once, with the engine kept loaded -- no wait
  and no second ready beep. Changing the model still reloads it, because that
  is the one change that needs it.

- The push-to-talk button now belongs to the app alone. A mouse side button
  used for dictation no longer also sends your browser Back, and a key like
  Scroll Lock no longer does its usual job while bound. Shift, Ctrl, Alt and
  the Windows keys still trigger dictation without being taken, because
  taking them would break every shortcut that uses them. No separate
  remapping tool such as AutoHotkey is needed to get a clean button.

- Speech is always transcribed as English. large-v3 no longer guesses the
  language on every clip, which cost it an extra pass.

- Install no longer creates a virtual environment. `vdict_install.bat`
  installs the packages into the Python on PATH, and the shortcuts run that
  Python.

- Development audio recordings moved from `userdata/flac` to
  `userdata/voice_recordings_PRIVATE`, filed in one folder per day. A toggle
  recording abandoned after two minutes now keeps its audio instead of
  discarding it.

- The transcript log now starts a new file each midnight and keeps the last
  thirty days, instead of growing to 100 MB and keeping the last five files.
  Each day's transcripts are in a file named for that day, so finding what you
  dictated on a given date no longer means scrolling through a single enormous
  file. Nothing to run and nothing to configure -- old days drop off on their
  own.

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
  different model or switch to CPU in Settings, then Save --
  instead of just naming the underlying error.

- The output window opens with a header naming the push-to-talk mode and
  trigger, the hotkey, the compute device, and the model. The model line
  carries its real size on disk, which is what tells you a large model will not
  fit in your GPU; it reads bare until that model has been downloaded.

- Saving Settings no longer reprints the welcome banner, which made the log look
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

- Copying in any app right after a dictation no longer freezes that app for
  five seconds. The engine owned the clipboard after putting your text back
  but was not listening for Windows' notice that you had replaced it, so
  Windows waited for a reply and gave up. It listens now.

- Dictating no longer destroys what you had copied. Whatever was on the
  clipboard -- text, an image, formatting, a file copied in Explorer -- is put
  back as soon as the program you dictated into has taken the text. Dictations
  also stay out of the Win+V clipboard history. The old setting that was
  supposed to control this only ever handled plain text and never ran, and it
  is gone; nothing replaces it, because there is nothing left to switch off.

- The app no longer records your voice to disk unless you deliberately turn it
  on. A development flag for collecting audio samples shipped switched on, so
  any copy of the source recorded every dictation as an audio file. Recording
  now requires a file that is not part of the app and is never copied with it,
  so a folder handed to someone else records nothing.

- Closing Settings no longer undoes changes made while it was open. The
  dialog used to write back a copy of your settings taken the moment it
  opened, so anything altered in the meantime was silently reverted --
  resize the output window, hide it to the tray, then Save, and
  it came back at its old size and text size. Every way of closing Settings
  was affected: Save, Escape, and the X.

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
  Save.

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

- A failed transcription no longer ends the session. Whisper occasionally
  raises on a given recording; the daemon now logs the error, writes a full
  traceback to the error log, and waits for the next button press instead of
  crashing.

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
