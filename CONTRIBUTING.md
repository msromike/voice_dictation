# Contributing

PRs welcome.

## Where to start

- `docs/backlog.md`: ideas worth building, grouped by what they're for.
- `docs/spike-notes.md`: things already measured.

## Setup

Windows only. Run `vdict_install.bat`, then install the checking tools:

    python -m pip install -r requirements-dev.txt

## Before you send a PR

All three must be clean:

    python -m ruff check .
    python -m pyright
    python tools\check_docstrings.py

## Code rules

- Catch errors only at things the app doesn't control: files, devices,
  Windows, other processes, user input. Inside the app's own code, let it
  crash.
- To satisfy pyright about something that may be None, assert it. Don't add
  an if-guard.
- Build paths relative to the file they're in, never from the working
  directory.
- A missing package gets installed and added to requirements.txt, never
  worked around.
- Docstrings and comment blocks are two lines at most.
  `tools\check_docstrings.py` enforces it.
