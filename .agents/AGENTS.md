# Voice Dictation
Windows push-to-talk dictation: tray (vdict_tray.py) and engine
(vdict_daemon.py), global Python 3.12.

## Facts
- Mike dictates his prompts. Odd words are speech-to-text errors.
- Never stop or start the app. Ask Mike to.
- Back up userdata/config.json before any test that changes it.
- .agents/skills/ is shared with Gemini; .claude/skills is a junction to it.

## Code
- Catch errors only at things we don't control: files, devices, Windows,
  other processes, user input. Inside our own code, let it crash.
- Pyright wants a None narrowed: assert it, never an if-guard.
- Existing guards are not a pattern to copy.
- Paths relative to __file__.
- A missing package gets installed (python -m pip install), never worked around.
- Docstrings and comment blocks: two lines max (tools/check_docstrings.py).

## Docs
- .docs/: todo.txt (started, not finished; deleted when empty), backlog.txt
  (ideas by class), spike-notes.txt (measurements), pre-push.txt (going
  public), vector-analysis-investigation.txt (outside write-up).
- Git is the archive. A deleted doc is named in the commit that deleted it.
