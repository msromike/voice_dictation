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
No retention exists. Keep recording; two later items read the captures
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
Two processes become one with worker threads, which is what core-arch
wanted. What carries over unchanged: the corpus writer (plain SQLite), the
STT engine (faster-whisper), and pynput in the capture thread, because
push-to-talk must fire while unfocused and no widget event can do that.

## Order

Three versions. v1.0 is done when the son runs it all day at home and at
work without Mike in the room.

### v1.0

1. Doc cut, by draining. A file is never summarized on the way out. Each
   paragraph gets a destination or an explicit delete, shown as a table
   before anything moves, and the file goes only when its table is empty.
   Done: backlog.txt walked. Its polish items live in qt-port-plan.txt
   POLISH, its ambient items in ambient-plan.txt, B5 in pre-push.txt P1,
   its measurements in spike-notes.txt. Three unowned entries remain in
   backlog.txt.
   Outright, nothing to drain: _schema.txt, doc-prune-plan.txt,
   doc-prune-build-sheet.txt, defects.txt, the ENTRY gates in the
   build-sheet template, and the discuss, explain and deconstruct skills.
   Still to walk: core-arch-plan.txt and input-device-plan.txt (into the
   Qt plan), roadmap.txt (into this file), handoff.txt (TESTING into
   CLAUDE.md), pre-push.txt P10 (names files and a skill that no longer
   exist). Every walked paragraph gets survival (does it still make sense
   with Tk, sounddevice and the second process gone) and cost (does Qt
   make it cheaper or dearer). Close the corpus sheet: tick STEP 2, run
   STEP 3 cleanup, delete tools/migrate_flac_corpus.py, write the missing
   CHANGELOG entries, fix the version declared twice.

2. Inference tuning, both arms, from its existing sheet. The app ships
   float32 on CPU and has never measured which compute type wins per
   device class. Targets: this machine on GPU and on CPU (CPU while
   gaming), the son's desktop, his laptop, his work desktop. Touches
   stt.py only, which the port carries over unchanged.

3. Qt rewrite. One process, PySide6, one QSS file. Exit gate: the app Mike
   uses today, working the same, on Qt, existing model and compute
   dropdowns included. Built alongside the Tk tray with a throwaway
   launcher, switched at the entry point, Tk deleted at cleanup. Before
   the build sheet: the one-sitting read of Qt's examples against the
   parity inventory, from the plan's SCRATCHPAD.

4. B6 clipboard delivery, from backlog.txt. Every dictation destroys the
   clipboard today, and the restore switch only ever handled text. Save
   and restore every format, let Windows say when the paste landed, gate a
   re-press during a busy cycle, tones that say what happened. Deletes
   the preserve_clipboard switch.

5. Ambient plan from ambient-plan.txt, then phase one built in the Qt
   app: continuous capture in chunks, background transcription that does
   not need real time, retention as a size budget, default unlimited. The
   B29 corpus switch and B30 budget are its Settings controls.

6. Portable folder. Model directory and interpreter inside the tree,
   model loaded by path. The embeddable interpreter loads CUDA from its
   own site-packages; measured, in spike-notes.txt.

7. Day view. What got recorded today, as text, in a text editor. The
   product before speakers exist.

8. Polish a new user hits on day one, from qt-port-plan.txt POLISH:
   B29 corpus switch he can see and turn off; B14's transcript toggle and
   the what-this-records disclosure; B8 X hides to tray, never stops
   recording; B19 mic test with a level meter; B30 retention control.

### v1.1

9. Attribution, per B24's three tiers in ambient-plan.txt: Speaker A/B
   labels, then persistent voice GUIDs with a GUID-to-name table the user
   fills in one row at a time.

10. Lookup by person and day. What Bob said, on what date, with the text.
    A query on the captures table's speaker, start_time and text columns
    once tier three fills the speaker column.

11. Pre-push from pre-push.txt, then decide whether to ship.

### v1.2

12. Search by meaning, B28 in ambient-plan.txt.
    vector-analysis-investigation.txt is its input and stays until the
    search plan drains it.
13. Voice prompt mode B26 and selection transform B27, ambient-plan.txt.
14. Punctuation rescue B13 and phonetic correction B21, backlog.txt. Both
    wait on corpus measurements ambient produces for free.
15. Remaining POLISH in qt-port-plan.txt: B1 settings tiering, B3 tone
    sliders, B11 settings and output together, B17 and B22 model dropdown
    curation, B20 relaunch raises the window, B23 settings layout.

## Rules for this file

One line per item: the thing and why. Design happens when an item reaches
the front of the order, in its own plan. Items get deleted when done, not annotated.
Git holds the history.
