# Going public

The public repo is a fresh one made from a cleaned copy, never this one:
this repo's history holds config.json and the dictation database.

What ships: voice-dictation/, tools/check_docstrings.py, images/,
templates/, the .bat files, README.md, CHANGELOG.md, LICENSE,
requirements.txt, requirements-dev.txt, pyproject.toml, pyrightconfig.json,
.gitignore. Nothing else: no .docs, .agents, .claude, CLAUDE.md, GEMINI.md,
.vscode, dev-flags.toml, userdata.

Before the push:

1. `python -m ruff check .`, `python -m pyright`,
   `python tools\check_docstrings.py`: all clean.
2. Version bumped in vdict/__init__.py and vdict_daemon.py, both the same.
   CHANGELOG [Unreleased] becomes that version with a date.
3. README matches the app: no menu label or button text the code no longer
   uses, and a short section naming the three files that hold the user's
   own words (voice_recordings_PRIVATE, dictation_history_PRIVATE.db,
   logs/transcript_log.txt) and how to turn each off.
4. Clean clone into an empty folder, run vdict_install.bat, launch from the
   Desktop shortcut, dictate once. Run startup_folder_uninstall.bat and
   confirm the Startup shortcut is gone. Make a stick and install from it
   on another machine.
5. Grep the cleaned copy for "msromike", "C:\bin" and "C:\Users".
6. dev-flags.toml is absent from the copy.

After the push: set the repo description and a few topics (speech-to-text,
dictation, whisper, push-to-talk, windows, offline). Confirm the Help menu's
GitHub link resolves. Later, if anyone asks: a Releases zip of the stick
folder, so nobody needs a working install first.
