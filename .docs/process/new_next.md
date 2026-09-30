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

1. Doc cut, by draining. A file is never summarized on the way out. Each
   paragraph gets a destination or an explicit delete, shown as a table
   before anything moves, and the file goes only when its table is empty.
   Outright, nothing to drain: _schema.txt, doc-prune-plan.txt,
   doc-prune-build-sheet.txt, defects.txt, pre-push P1, the ENTRY gates in
   the build-sheet template, and the discuss, explain and deconstruct
   skills.
   Walked: backlog.txt, core-arch-plan.txt and input-device-plan.txt (into
   the Qt plan), roadmap.txt (into this file), handoff.txt (TESTING into
   CLAUDE.md). Every walked paragraph gets two questions from the Qt
   plan's old reading passes: survival (does it still make sense with Tk,
   sounddevice and the second process gone) and cost (does Qt make it
   cheaper or dearer). Backlog's rejection blocks get a third, revival:
   was it refused for a reason one process or Qt removes. X-to-tray and
   the volume mixer refused over four pythonw entries are two known
   reopeners.
   Before backlog.txt goes, one pass moves its measured facts to
   spike-notes.txt: the rpunct dead end, the 88 ms restoration number, the
   metaphone collisions, the 3070 Ti GPU tests. B24, B26, B27 and B28 move
   whole, design included, into ambient-plan.txt as its seed. Nothing in
   them is cut to a line. Close the corpus sheet:
   tick STEP 2, run STEP 3 cleanup, delete tools/migrate_flac_corpus.py,
   write the missing CHANGELOG entries, fix the version declared twice.
   Commit with the three changes already uncommitted.

2. Spikes still open. Each answer goes to spike-notes.txt and closes the
   BLOCKED item in qt-port-plan.txt that names it. Hotkey, GPU release,
   embeddable CUDA and the audio path are measured and settled.
   - Mic hotplug, reboot half only. The signal fires and the id survives
     replug, measured. One id comparison after the next restart decides
     whether config carries the id beside the name.

3. Inference tuning, from its existing sheet. The app ships float32 on CPU
   and has never measured which compute type wins per device class. GPU arm
   decides all-day throughput on the son's card; CPU arm decides the work
   desktop if it has no card. Touches stt.py only, which the port carries
   over unchanged, so it runs before Qt without being done twice.

4. Qt rewrite. One process, PySide6, one QSS file. Exit gate: the app Mike
   uses today, working the same, on Qt. Built alongside the Tk tray with a
   throwaway launcher, switched at the entry point, Tk deleted at cleanup.

5. Ambient plan, then phase one built in the Qt app: continuous capture in
   chunks, background transcription that does not need real time, retention
   as a size budget. Attribution and search are phases two and three of the
   same plan.

6. Portable folder. Model directory and interpreter inside the tree,
   model loaded by path. The embeddable interpreter loads CUDA from its
   own site-packages; measured, in spike-notes.txt.

7. Handoff polish, the items from the old NEXT.txt that a new user hits
   first. All after Qt, built once in the Qt tray:
   - Live shared config. Settings read from one object instead of
     re-reading disk; stops every settings change paying a full model
     reload.
   - Input device rebuild. Mic list refreshes live, no Windows-default
     trap.
   - Settings dialog grouped by function instead of one long stack.
   - Model dropdown: curated list, device-aware, with a show-all hatch.
   - Tone volume sliders, start and stop. Two hard-coded constants today.
   - Mic test button with a level meter in Settings.
   - X hides to tray, minimize goes to taskbar, Exit exits. Today X kills
     the daemon.
   - Settings and the output window open and close together.
   - A View-menu toggle for transcript logging, and the disclosure: the
     log records every transcript and nothing says so.
   - Corpus opt-in switch the user can see and turn off.
   - FLAC retention as a size budget the user picks.

8. Attribution, per B24's three tiers: transcription only, then Speaker
   A/B labels, then persistent voice GUIDs with a GUID-to-name table the
   user fills in one row at a time.

9. Lookup by person and day. What Bob said, on what date, with the text.
    A query on the captures table's speaker, start_time and text columns,
    nothing more, once tier three fills the speaker column. Output to a
    text editor.

10. Search by meaning. Pipeline sketch from the old NEXT.txt: Whisper to
    sentence-transformers to SQLite nearest rows, Ollama summary optional,
    paste into Notepad. vector-analysis-investigation.txt is the input to
    this plan and stays until it drains.

Later, from the old NEXT.txt, unordered:
   - Relaunch raises the running window instead of saying already running.
   - Clipboard delivery done right: restore images and files, refuse a
     re-press during a busy cycle, tones that say what happened.
   - Punctuation rescue for run-on transcripts. Measure incidence first;
     the captures table can answer it now.
   - Phonetic vocabulary correction, so Tray stops coming out Trey. Needs
     a second signal before swapping; cloud collides with Claude.
   - Selection transform: select text, PTT, speak an instruction, Whisper
     plus selection to Ollama, output pastes over the selection.
   - Pre-push checklist, then decide whether to ship. Still owes a demo
     clip, a what-this-records section in the README, and repo topics on
     push day.

## Rules for this file

One line per item: the thing and why. Design happens when an item reaches
the front of the order, in its own plan. Items get deleted when done, not annotated.
Git holds the history.
