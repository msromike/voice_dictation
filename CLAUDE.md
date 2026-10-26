# Voice Dictation
Windows push-to-talk dictation: tray (vdict_tray.py) and engine
(vdict_daemon.py), global Python 3.12.

## Facts
- Mike dictates his prompts. Odd words are speech-to-text errors.
- Never stop or start the app. Ask Mike to.
- Back up userdata/config.json before any test that changes it.

## Code
- Code rules: CONTRIBUTING.md. Change a rule there, never here.
- Existing guards are not a pattern to copy.

## Repo
- This repo is public. userdata/ and dev-flags.toml are never tracked.
- The history before 2026-10-26 held userdata; it was removed from every
  commit. The uncleaned history is the bundle in C:\bin\archive, never pushed.

## Docs
- docs/ is Markdown: backlog.md (ideas by class) and spike-notes.md
  (measurements).
- Git is the archive. A deleted doc is named in the commit that deleted it.
