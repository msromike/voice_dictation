# Voice Dictation
Windows desktop PTT daemon.

## Commit Protocol
Use the `commit-per-protocol` skill, not the global Commit Protocol.

## SPOP
Propose chunks (end with question) -> approved -> implement 1 -> STOP -> "works" -> implement 2 -> STOP
Never propose+implement same turn.

## Code
- crash-fast: no null checks between internal modules
- validate at boundaries only (config.json, audio device, model input)
- install deps immediately; no workarounds
- no emojis, anywhere; docs TXT (MD needs permission)

## Lint
The edit hook ignores C901, PLR09 and RUF100 on purpose. Complexity is not shown
while writing -- a half-built function invites reshaping to move a number instead
of finishing the work. It runs at commit instead, on finished code.
Do not remove the ignore.

## Claims
No lock words -- settled, locked, decided, rejected, cannot happen, do not relitigate.
Anything unverified says UNVERIFIED.
Applies to what I say, not only to what I write in files.
Record decisions with the reason that would overturn them: what was chosen, what
it beat, why. Stops re-derivation, not questioning. Build sheets: ALREADY WEIGHED.

## Docs
backlog.txt = work to do.    Drains to empty. A reminder, not a design doc.
defects.txt = wrong now.     Drains to empty.
Done = app runs + backlog empty + defects empty.
A backlog entry is a few lines. Design goes in a build sheet when the item comes up.
Mike deletes the sheet himself, once it is no longer needed.
NO LINE NUMBERS in docs. Name a greppable symbol.
Durable facts go in a code comment at the point of temptation

## Processes
venv\Scripts\pythonw.exe is a redirector stub -- every logical process appears TWICE.
Four pythonw = normal. Filter on "vdict", not "voice_dictation".
