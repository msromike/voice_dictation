# Voice Dictation: vision and next steps

Written 2026-09-29 after a month away. Replaces roadmap.txt and NEXT.txt
once the doc cut lands. The cold read that produced this is in git history
under this file's first commit.

## Where it stands

The app works and is in daily use: tray and daemon running, a transcript log
every day since Aug 30, the history database written tonight, no error since
Aug 10. Last code commit was 5e7e175 on Aug 10, which landed the capture loop
cleanly. Everything after it was documentation. Nothing in code is
half-built.

The corpus flag is on and has been since Aug 3: 44,783 FLAC files, 6.2 GB.
No retention exists. Keep recording; later items read the captures
table.

## The vision

Ambient mode is the point. The target user is Mike's son: a GPU desktop at
home, possibly a desktop at work, one folder he copies. He wants everything
spoken in his office and on calls recorded, searchable, with speaker
attribution when it comes. Push-to-talk stays as it is; ambient is a second
mode beside it. The corpus table already carries a mode column and a speaker
column for this.

Qt comes first, before ambient, and it is a rewrite, not a tray swap. The
reason is the AI cliff: hand-rolled glue on hand-rolled glue until the model
can no longer hold the picture. Ambient roughly triples the daemon. Building
that on the current Tk and sounddevice glue and porting afterward is doing
it twice. So the port removes the glue from both halves first, and ambient
lands on documented library calls.

What the rewrite deletes, per qt-port-plan.txt: sounddevice for
QAudioSource and QAudioSink; the stdout wire protocol and the 100 ms drain
for signals; pystray, geometry.py, dpi.py, the WAV tone machinery, the
win32event mutex, pyperclip, and the two Tk clipboard paths for Qt calls.
Two processes become one with worker threads, which is what the retired
core-arch plan wanted. What carries over unchanged: the corpus writer (plain SQLite), the
STT engine (faster-whisper), and pynput in the capture thread, because
push-to-talk must fire while unfocused and no widget event can do that.

## Order

Versions v1.0 through v2.3. The only users are Mike and his son; the repo
goes public when Mike decides it is done. v1.0 is done when the son dictates with it
all day at home and at work without Mike in the room.

Model per item. Fable when the item writes a plan or a build sheet, or
Mike rules on a design. Opus when the item runs a sheet, drains a doc, or
measures. Fable has its own usage limit, so opus is the default. At
session start, say which the front item calls for and which is running;
a mismatch is the first line of the report, before any work.

### v1.0 -- dictation on Qt

1. Doc cut, by draining. A file is never summarized on the way out. Each
   paragraph gets a destination or an explicit delete, shown as a table
   before anything moves, and the file goes only when its table is empty.
   Done: backlog.txt walked. Its polish items live in qt-port-plan.txt
   POLISH, its ambient items in ambient-plan.txt, B5 in pre-push.txt P1,
   its measurements in spike-notes.txt. Three unowned entries remain in
   backlog.txt.
   Still to walk: input-device-plan.txt (into the Qt plan), roadmap.txt (into this file). Every walked paragraph gets survival (does it still make sense
   with Tk, sounddevice and the second process gone) and cost (does Qt
   make it cheaper or dearer).

2. Qt rewrite. One process, PySide6, one QSS file. Exit gate: the app Mike
   uses today, working the same, on Qt, existing model and compute
   dropdowns included. Built alongside the Tk tray with a throwaway
   launcher, switched at the entry point, Tk deleted at cleanup.
   Done ahead of it: qt-port-plan.txt has no open spikes, blockers or
   scratchpad items, and three JUDGMENT items the core-arch drain moved in
   (the log signal's payload, a mic or model change mid-capture, the
   mic-fault modal); hand-rolled-ledger.txt rules every
   symbol (82 delete, 2 replace, 99 keep) and every SPIKE it raised is
   measured in spike-notes.txt except mixed-scale monitors, a first-launch
   check on the son's laptop; qt-parity-inventory.txt matches the code.
   Next: write the Qt build sheet from the ledger's DELETE and REPLACE
   rows plus the modularity section's nine boundaries.

3. B6 clipboard delivery, from backlog.txt. Every dictation destroys the
   clipboard today, and the restore switch only ever handled text. Save
   and restore every format, let Windows say when the paste landed, gate a
   re-press during a busy cycle, tones that say what happened. Deletes
   the preserve_clipboard switch.

4. Portable folder. Model directory and interpreter inside the tree,
   model loaded by path. The embeddable interpreter loads CUDA from its
   own site-packages; measured, in spike-notes.txt. Capture is off in a
   handed-out copy, so nothing is retained and nothing needs a switch.

5. Polish a new user hits on day one, from qt-port-plan.txt POLISH:
   B8 X hides to tray instead of killing the app; B19 mic test with a
   level meter; B14 transcript toggle and the what-this-records
   disclosure, since the transcript log is written on every machine;
   B31 a Welcome dialog, because first run today explains nothing and
   Mike won't be there to.

### v1.1 -- settings and window polish

6. Remaining POLISH in qt-port-plan.txt: B1 settings tiering (moving the
   Settings window reloads the model today), B11 settings and output
   together, B20 relaunch raises the window, B17 and B22 model dropdown,
   B23 settings layout, B3 tone
   sliders (may be deleted: one process is one mixer entry).

### v1.2 -- dictation accuracy and the corpus

7. Two corpus queries, run-ons and name misspellings, over the captures
   table that exists today. Each decides whether its fix gets built.
8. Punctuation rescue B13 and phonetic correction B21, backlog.txt, each
   only if its query shows it is needed. B21 still needs a second signal
   designed. The Ollama tuning workflow under B13 only if its defaults
   fall short.
9. Corpus opt-in B29 and retention budget B30, ambient-plan.txt. A corpus
    cannot be back-filled, so the son's starts filling here; ambient
    inherits the one switch and the one budget.

### v2.0 -- ambient

10. Ambient plan from ambient-plan.txt, then phase one built in the Qt
    app: continuous capture in chunks, background transcription that does
    not need real time, and a day view: what got recorded today, as text,
    in a text editor.

### v2.1 -- who said it

11. Attribution, per B24's three tiers in ambient-plan.txt: Speaker A/B
    labels, then persistent voice GUIDs with a GUID-to-name table the user
    fills in one row at a time.

12. Lookup by person and day. What Bob said, on what date, with the text.
    A query on the captures table's speaker, start_time and text columns
    once tier three fills the speaker column.

### v2.2 -- talking to a model

13. Voice prompt mode B26 and selection transform B27, ambient-plan.txt.
    Both need a local model, which stays home and does not travel in the
    portable folder.

### v2.3 -- search by meaning

14. Search by meaning, B28 in ambient-plan.txt. Needs ambient's corpus.
    vector-analysis-investigation.txt is its input and stays until the
    search plan drains it.

### No version

Pre-push from pre-push.txt, then the public-repo decision, whenever Mike
decides it is done.

## Rules for this file

One line per item: the thing and why. Design happens when an item reaches
the front of the order, in its own plan. Items get deleted when done, not annotated.
Git holds the history.
