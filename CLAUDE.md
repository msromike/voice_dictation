# Voice Dictation
Windows desktop PTT daemon.

## Commit Protocol
Use the `commit-per-protocol` skill, not the global Commit Protocol.

## SPOP
Per item: review the code it touches against current disk state -> explain it, grounded in
that review, not the doc alone -> end with a question naming the item -> approved -> implement
-> STOP -> report done/problems -> next item.
Never propose+implement same turn. Never explain an item from the build sheet's text without
first confirming it against the code as it exists right now.
Item boundary = risk seam, not feature size. Cross-process state (tray/daemon) or a required
ordering (reinit before resolve) -> own item, never bundled, even if one line would cover it.

## Planning
Discoverability beats turn count. Extra turns surface what a streamlined
pass would not -- never compress a gate to save one.
Measure before asking. A design question about unmeasured code gets asked twice.
Every recommendation: could someone execute this from this text alone?
End of every planning chunk: what is still open is either settled or written
where it is found without me.

## Verification
Config-forced tests: BAK AND RESTORE. Copy config.json to config.json.bak
before the edit, copy it back after. The app rewrites config.json on Settings
close, on hide and at exit -- a test that opens Settings persists the test
values, so restoring by hand loses real settings.

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

## Search
.docs/ is hidden+gitignored -- ripgrep skips it by default; .rgignore re-includes it.
