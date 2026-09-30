# Voice Dictation
Windows PTT daemon. Mike doesn't write Python. Explain in plain English,
consequence first.

## This machine
pythonw.exe shows twice per process. Filter on "vdict".
Don't start the app unless asked -- it's probably running. Say what to run.
voice_dictation-stable is his dictation fallback. Leave it frozen.
He dictates his prompts. Garbled words are transcription artifacts.
Everything the app writes is under userdata/. A test that forces a config
change backs up config.json first and restores it after he confirms the app
is down.

## Code
Crash-fast: no null checks between internal modules. Validate at boundaries
only -- config.json, audio device, model input.
Paths relative to __file__.
Install deps. No workarounds.
Commits use commit-per-protocol, never the global commit skill.
A lint gate on finished code: report the number, never restructure to pass.
Docstrings and comment blocks: two lines max. tools/check_docstrings.py
enforces it at commit.
Second special case in one function for the same reason -- ask whether
Windows already owns the problem.

## Reporting
DONE means I watched it work. Otherwise NOT DONE and why.
Say what ran and what only linted. Never one word for both.
Say "nothing found" rather than going quiet.
Never soften a finding by when it should be fixed.
Read the code before explaining it. A comment is a claim, not evidence.
Measure before asking.
Ask in prose, never the multiple-choice question tool.
Gates are oversight, never a schedule: do not pace work to fit them.
A choice with nothing to gain on one side is not a choice. Say what
you're doing and why; ask only when both sides cost something.

## Docs
Markdown. No line numbers, no emojis.
Drain, never summarize: a retired doc's paragraphs each get a destination
or an explicit delete, in a table shown first. Every row has a Source
column: the commit or file:line its reason came from, or UNVERIFIED.
Agents read .docs/agent-rules.md before any task.
Nobody else checks the docs for coherence. That is mine, unprompted.
