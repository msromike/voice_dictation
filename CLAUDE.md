# Voice Dictation
Windows desktop PTT daemon.

## Facts


## Directives
"commit per protocol"   -> commit-per-protocol skill
"discuss per protocol"  -> discuss-per-protocol skill
"explain per protocol"  -> explain-per-protocol skill
"explain step N"        -> propose only. Do not implement in the same turn.
"approve"               -> implement what was proposed
"execute all"           -> build the batch, one report at the end. Stop at the
                           first surprise.


## Rules
SPOP: one chunk at a time. Propose, wait for approval, implement, stop.
EDIT AUTHORIZATION: nothing written to disk without approval -- code, docs,
config. Approval is a prior turn. A proposal turn ends with a question or a
waiting statement, and calls no edit tool.
Tools passing is not the result. Report what it did.

DONE: you watched it do the thing. Otherwise the first line is NOT DONE and
why.

Before explaining or reporting on a chunk, read the code and the docs it
touches as they are right now. Never explain from a document's text alone.
If that means opening files before you can answer, open them. That read is
what catches a doc describing code that has since moved.

Every chunk of work -- from a build sheet, the todo list, or raised in
conversation -- runs in this order:
  Read the current state on disk of whatever it touches.
  Explain it, grounded in that read, not the doc alone.
  End with a question naming the chunk.
  On approval, implement.
  Stop.
  Report done or problems.
  Offer the next chunk.

Code disagreeing with the doc is a finding.
Surface it before the explanation, never reconcile it into one silently.

Extract every identifier in the chunk's text -- filenames, functions, classes,
config keys -- and grep .docs/ for each one.
Extract, never select. Which ones matter is not mine to decide.
Any file with a hit gets read whole, not just the matching line. The decision
that matters is often prose naming no identifier at all.
A doc disagreeing with another doc is a finding too, same as code.
Say what that grep returned, "no hits" included.
A check that is silent when clean cannot be told apart from one that never ran.

House Style: every line is one of these. Missing the half after the + means it
is not that shape. Headers and layout are not lines.
  FACT      what is true + how to confirm it
  RULE      trigger -> act + the tempting wrong turn
  DECISION  what was chosen + the evidence it rests on
  QUESTION  what is unknown + the method that answers it
  INTENT    what should exist + what changes when it does
  OPEN      none of the above. Report the OPEN count whenever shaping a doc.
A line contradicted by another gets marked CONFLICT, and nothing else.
Artifact-specific style is in the templates.


## Corrections
Explain in plain English, at recap length.
Name the expansion axes, do not spend them.
"Deeper on request: X, Y" says depth exists without paying for it.
Expansion axes are explanation depth only.
An open choice is a question, never a "deeper on request" note.
Approval turns that note into my own call, made where you cannot see it.


==============================================================================
UNSORTED BELOW THIS LINE
==============================================================================



## SPOP
THREE ACTS GOVERN WHAT REACHES MIKE. Acts, not qualities -- the quality versions of
these drifted for a whole session with every rule above loaded.
  FILTER. Before presenting anything as settled, write both sides and name a
  winner -- and show that pricing. Never act on it silently: his reaction to how
  I priced it is where a problem I could not see gets caught.
  GATE. Two or more open items in one turn -> all of them enter TodoWrite before
  any is spoken, exactly one in_progress, and only that one appears in the reply.
  A single open item is the closing block above. Something found mid-turn enters
  the list, never the reply.  A live list survives tangents and is never cleared by one. Work a tangent spawns enters the list rather than replacing it, and resuming names the position and the count out loud -- he forgets what was settled too, and the list is shared state, not my private discipline. An item that gets no answer stays open and gets re-raised. Silence is not a ruling; recording it as one puts words in his mouth that get cited later. BLOCK. A decision turn is exactly: Problem. / What I'll do. / Approve? -- or, when alternatives genuinely exist, those options with a REC. A recommendation with no alternatives is a false choice.

Explain closes with a fixed block, in order: what changes on disk, concrete enough to reject -- then BLOCK, or the words "nothing open". Never a third thing.
Report names what ran separately from what linted. Never one word for both.
Report ends with the gesture to run, or "no launch test this step". Never implied.
Item boundary = risk seam, not feature size. Cross-process state (tray/daemon) or a required ordering (reinit before resolve) -> own item, never bundled, even if one line would cover it.

## Planning
Discoverability beats turn count. Extra turns surface what a streamlined
pass would not -- never compress a gate to save one.
Measure before asking. A design question about unmeasured code gets asked twice.
Any claim of the form "every X" is derived from the source, never hand-listed --
extract the set, then assert.
Every recommendation: could someone execute this from this text alone?
A decision that closes a path is read against backlog and roadmap first. Work
named there is a constraint on it, not a hypothetical.
An unmeasured claim gets presented with what a spike would cost. Mike chooses
settle or defer -- silent deferral is what turns cleanup into a sweep.
End of every planning chunk: what is still open is either settled or written
where it is found without me.

An investigation chunk reports findings, each carrying a disposition. A bare
list is not a report -- ordering by discovery hands the sorting back to Mike.
Dispositions come from the material, never a fixed set. A finding that fits no
bucket means a missing bucket or a finding not yet understood -- say which.
Open with how the item's own premise held. Nothing else validates the next
item before it is run.
A finding that differs states three things: what was assumed, what was found,
and whether it is open for discussion or already decided and awaiting approval.
A finding surfaced mid-discussion re-enters as a finding. Absorbing it into the
step in flight is how a premise correction gets lost.
Too coarse is counted in decisions, not findings. More than two needing a
decision means the item should have been split.
Disk preview shows every line that came from a decision and every line whose
phrasing I invented, mechanical lines skipped. A sample I pick for confidence
proves nothing.
After the write, re-read for what the edit broke. Report what that found,
"nothing" included.

## Code
- crash-fast: no null checks between internal modules
- validate at boundaries only (config.json, audio device, model input)
- install deps immediately; no workarounds
- no emojis, anywhere; docs TXT (MD needs permission)
- paths relative to __file__; the tree runs from any folder on the machine

## Lint
The edit hook ignores C901, PLR09 and RUF100 on purpose. Complexity is not shown
while writing -- a half-built function invites reshaping to move a number instead
of finishing the work. It runs at commit instead, on finished code.
Do not remove the ignore.

## Claims
Settled, locked, decided, rejected, cannot happen, do not relitigate -- these are
lock words when they stand alone. Carrying the condition that would overturn them
is what makes the same word a record instead of a bar on asking. A condition
nobody would notice reaching is not a condition.
Anything unverified says UNVERIFIED.
Applies to what I say, not only to what I write in files.
Record decisions with the reason that would overturn them: what was chosen, what
it beat, why. Stops re-derivation, not questioning. Build sheets: ALREADY WEIGHED.

## Docs
backlog.txt = work to do.    Drains to empty. A reminder, not a design doc.
defects.txt = wrong now.     Drains to empty.
Package question raised and answered "not now" -> one line in spike-notes.txt
TOOLKIT GAPS: what stays hand-rolled, which library gap forced it, why not now.
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
Writing a build sheet starts by copying .docs/templates/build-sheet-template.txt. Copy it,
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

## Output Window
It is the OUTPUT WINDOW. The code says console and that word is a false model --
not a terminal. One "category|text" line printed, a reader thread draining, an
unbounded queue, a 100ms Tk timer painting. Nothing types into it, nothing blocks
on it. Reasoning from the word cost a phantom hazard once.
TEMPORARY: the Qt port renames the code. Delete this section then.

## Processes
venv\Scripts\pythonw.exe is a redirector stub -- every logical process appears TWICE.
Four pythonw = normal. Filter on "vdict", not "voice_dictation".

## Search
.docs/ is hidden -- ripgrep skips it by default; .rgignore re-includes it.
Tracked in git on purpose during development. Gitignored before the push.
