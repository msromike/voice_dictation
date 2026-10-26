# Voice Dictation

The app provides speech-to-text transcription on your local machine and injects it at the cursor. Written in Python and uses the faster-whisper automatic speech recognition (ASR) model. No trip to the cloud. Can run on a CUDA-capable GPU or on CPU. Response on GPU with a large model is virtually instant on GPU, similar speed with smaller models on CPU.

NOTHING LEAVES YOUR MACHINE. Once your speech model has downloaded, internet access is not required.

## Install, and update

1. On this page, click **Code > Download ZIP**.
2. Unzip it. You get a folder named `voice_dictation-main`; that's the app.
3. Double-click `vdict_install.bat`. If Windows says "Windows protected your
   PC", click **More info**, then **Run anyway**.

To update, double-click `update.bat` in the app folder. If the app is running,
it asks before closing it. It downloads the latest version, keeps your
settings and history in `userdata`, runs the installer, and starts the app.

The installer installs Python 3.12 if you don't have Python
3.10 or newer already installed, then about 1.4 GB of packages, most of which are NVIDIA libraries. The installer creates a **Voice Dictation** shortcut on the Desktop and starts the app at login. Run `startup_folder_uninstall.bat` if you don't want it to automatically run. You can also start the app with `vdict_run.bat`.

## First run

On first run, Settings opens by itself. Pick your microphone and choose your PTT button. You can also poke around with some of the other settings here, but the PTT button must be set by you.

If you have an NVIDIA card, switch Compute device to GPU and the model to
large-v3, which is more accurate. On CPU, `base.en` works quite well.

Speech models are downloaded as you select them, so feel free to try different ones.

## Usage

Place your cursor where you want the text, press the key or mouse button you selected for PTT, speak and release. I use mouse side buttons for PTT and to send Enter. A high beep means it's recording, a low beep means it stopped.

There are a few QOL keybinds to paste the last dictation if your cursor was not focused, or to raise the output window so you can scroll and copy-paste previous transcriptions. The output window has some interesting capabilities as well.

## Your data

Everything the app writes is in `userdata` next to it:

- `config.json`: your settings. Delete it to start over.
- `vocabulary.txt`: words it should spell your way. File > Vocabulary.
- `logs\transcript_log.txt`: every dictation, as text. There is no switch
  for this yet; delete the file if you don't want it kept.
- `logs\event_log.txt` and `logs\tray_error.log`: notes and errors, never
  your dictated text.

### Keeping your recordings

Off unless you turn it on: rename `dev-flags.example.toml` to
`dev-flags.toml` and every dictation is also kept as audio in
`voice_recordings_PRIVATE`, with a row in `dictation_history_PRIVATE.db`
recording its timing, model, transcript and target window. Delete
`dev-flags.toml` to stop.

Why you might want it:

- A corpus of your own voice, paired with what the model heard. Test a
  different speech model or setting against your real dictations instead
  of a benchmark.
- A searchable history. The database is plain SQLite, so any SQLite tool
  can query what you said, when, and into which window.
- A head start if you fork this. Anything that learns from your speech,
  such as tuning or voice ID, needs recordings that already exist, and they
  can't be collected after the fact.

What it costs:

- Disk. All-day use comes to about 35-40 GB of audio a year, and nothing
  prunes it; delete old day folders by hand.
- Privacy. It's your voice and the titles of the windows you dictated into,
  sitting on disk. Nothing leaves the machine, but anyone with access to
  the folder can read and play it.

## Limits

- It can't type into a window running as administrator.
- With no text field focused, nothing pastes. The dictation is in the output
  window, or bind the Paste last dictation hotkey in Settings and press it
  where you meant it to go.
- GPU needs an NVIDIA card.

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the checks to run and
[the backlog](docs/backlog.md) for ideas.

## License

MIT. See LICENSE.
