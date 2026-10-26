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

## Repos
- This is the private repo, voice_dictation-dev. Its history holds personal
  data, so it is never made public.
- The public repo, voice_dictation, is built by tools/publish.py from an
  allowlist. Never push this repo's history there.

## Docs
- .docs/ is Markdown: backlog.md (ideas by class) and spike-notes.md
  (measurements). Both ship to the public repo under docs/.
- Git is the archive. A deleted doc is named in the commit that deleted it.
