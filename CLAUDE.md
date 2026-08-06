# Voice Dictation
Windows desktop PTT daemon.

## Commit Protocol
Use the `commit-per-protocol` skill, not the global Commit Protocol.

## SPOP
"Explain step N" / "next step" = propose only. "Approve" = implement.
Per item: review the code it touches against current disk state -> explain it, grounded in
that review, not the doc alone -> end with a question naming the item -> approved -> implement
-> STOP -> report done/problems -> offer the next item.
Never propose+implement same turn. Never explain an item from the build sheet's text without
first confirming it against the code as it exists right now.
The re-review IS a review. Code disagreeing with the sheet is a finding -- surface it before
the explanation, never reconcile it into one silently.
Per item, grep .docs/ for the symbols that item moves. A doc disagreeing with the sheet is
a finding too, same as code. Catches a contradiction at the step that causes it, not at the
cleanup step nine items later.
The report says what that grep returned, "no hits" included. A check that is silent when
clean cannot be told apart from one that never ran.
Explain in plain English, at recap length. Name the expansion axes, don't spend
them -- "deeper on request: X, Y" says depth exists without paying for it.
Expansion axes are explanation depth only. An open choice is a question, never a
"deeper on request" note -- approval turns that note into my own call, made where you
cannot see it. Two open choices -> ask one, carry the other.
Explain closes with a fixed block, in order: what changes on disk, concrete enough to
reject -- then either one open choice as options with a REC, or the words "nothing
open". Never a third thing.
Report names what ran separately from what linted. Never one word for both.
Report ends with the gesture to run, or "no launch test this step". Never implied.
Item boundary = risk seam, not feature size. Cross-process state (tray/daemon) or a required
ordering (reinit before resolve) -> own item, never bundled, even if one line would cover it.

## Planning
Discoverability beats turn count. Extra turns surface what a streamlined
pass would not -- never compress a gate to save one.
Measure before asking. A design question about unmeasured code gets asked twice.
Any claim of the form "every X" is derived from the source, never hand-listed --
extract the set, then assert.
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
An observation inside a live plan's scope goes into that plan, not backlog --
backlog is for work with no owning plan. Capture it there when found; the
plan's own true-up integrates it. Waiting for the true-up to rediscover it
is how it gets lost.
Done = app runs + backlog empty + defects empty.
Defects drain at the end of the build sheet that owns the code, before the next
plan starts. pre-push.txt's empty-defects gate is the outer bound, not the
cadence. A defect whose sites relocate mid-sheet drains after they land, so each
one is touched once.
No sheet owns the code, or it loses data or blocks launch -> drains now. Waiting
on a boundary it does not have is how a defect becomes push-only by accident.
A backlog entry is a few lines. Design goes in a build sheet when the item comes up.
Writing a build sheet starts by copying .docs/templates/build-sheet.txt. Copy it,
fill the slots, delete its HOUSE STYLE block at the end. Never write one from
scratch or from another sheet -- that is how the gates went missing.
Mike deletes the sheet himself, once it is no longer needed.
NO LINE NUMBERS in docs. Name a greppable symbol.
NO BARE TAGS in docs. The title is the identifier -- "the vdict_tray.py split",
not "P4". Tags are conversational shorthand; nothing durable depends on one.
One letter, one series. B=backlog, D=defects, P=pre-push. A new series never
reuses a taken letter.
Durable facts go in a code comment at the point of temptation

## Build order
.docs/process/roadmap.txt holds the order of the work and why. Read it before
proposing what comes next -- it changes far more often than this file, and a
second copy of the order here is how it went stale in a day.

## Processes
venv\Scripts\pythonw.exe is a redirector stub -- every logical process appears TWICE.
Four pythonw = normal. Filter on "vdict", not "voice_dictation".

## Search
.docs/ is hidden -- ripgrep skips it by default; .rgignore re-includes it.
Tracked in git on purpose during development. Gitignored before the push.
