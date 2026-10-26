# Backlog

Things that might get built someday, grouped by what they are for and
ordered by how much they would matter to someone dictating every day.

## A. INSTALLING

### A PRIVATE PYTHON WITH UV
  vdict_install.bat installs a normal Python for the whole account when none
  is found: it goes on PATH, shows in Add/Remove Programs, and is shared with
  anything else on the machine. Instead, fetch a pinned uv.exe with curl
  (built into Windows 10 and 11) and have uv put Python 3.12 and the packages
  inside the app folder. uv's Python includes Tkinter, which the smaller
  "embeddable" Python lacks. Nothing on PATH or in the registry; uninstalling
  is deleting the folder, and uv installs packages much faster than pip.
  vdict_run.bat and both shortcuts then point at the private pythonw. Open
  questions: whether uv needs a virtual environment inside the app folder to
  install packages, and how vdict_run.bat chooses between the private Python
  and a developer's own. While it's in there, the installer could also
  download the default speech model, so a fresh install works offline.

## B. PICKING DEVICES AND ENGINES
Settings knowing about the hardware it is running on. The mic fault is the
one failure a novice hits, and today it quits the app.

### MIC HANDLING WITHOUT A RESTART
  A missing or unopenable mic exits the engine and shows a modal that
  quits; the next launch reads a flag file and opens Settings. Instead:
  the engine never exits on a mic fault, the modal opens Settings, the
  user picks a device and the open is attempted right there, and a
  failure says so inline. The dropdown refreshes every time it opens, so
  plugging in a mic is the whole hot-swap story. No "System Default"
  entry, because Windows' default does not reflect intent (a webcam
  promoted itself, twice). One module owns every audio-device call; the
  primitives exist unwired in vdict/daemon/portaudio_io.py.
  spike-notes.md MICROPHONE DEVICES.

### MIC TEST BUTTON WITH A LEVEL METER
  A Test button next to the mic dropdown: click, speak, watch a bar. The
  convention every voice app uses. For the device that opens fine but is
  routed wrong, which today shows up as dictating and seeing nothing.

### MODEL DROPDOWN THAT KNOWS THE DEVICE
  Five hardcoded models. CPU and GPU users want different lists, turbo
  fits no tier, and a "show all" option would expose the rest. The real
  question is the axis: the user is choosing how good and how fast their
  English is, not a VRAM budget. spike-notes.md WHISPER MODEL LADDER.

## C. TRANSCRIPT ACCURACY
The words came out wrong or incomplete. Each of these is a post-process or
a better hint, and each should be counted in the captures table before it
is built: the table exists and the query is cheap.

### PUNCTUATION RESTORATION FOR RUN-ONS
  Rising intonation reads to Whisper as "not finished", so some speakers
  get long transcripts with no punctuation. Candidate: a small restoration
  model gated by a sentence-length check, so Whisper's own punctuation is
  trusted unless a transcript collapses into one giant sentence. Spiked;
  one of 52 real lines was flagged, and HOLD mode may already prevent
  most of it. spike-notes.md PUNCTUATION RESTORATION.

### PHONETIC CORRECTION FOR HOMOPHONES
  Whisper hears the right sound and picks the wrong spelling: Trey for
  Tray. A text post-process after every dictation that swaps a word for a
  vocabulary.txt entry with the same phonetic code. Spiked with jellyfish;
  bare code equality rewrites everyday words to names (cloud and clod both
  collide with Claude), so it needs a second signal that nobody has
  designed. spike-notes.md PHONETIC CODES COLLIDE.

### LIVE VOCABULARY
  vocabulary.txt is read once at engine start, so a new term needs a
  reload before it works, which is why it does not get used in the moment
  a term is missed. Read it on every dictation instead; the cost is under
  a millisecond. Nice to have: a note when the file is over Whisper's
  prompt limit, since only the last 223 tokens reach the model and the
  rest are dropped silently. spike-notes.md VOCABULARY.

## D. SHELL PREFERENCES
The shell already explains itself: X asks before exiting, first run opens
Settings and Save refuses to close until a PTT button is bound, the README
covers the rest. These are preferences about how it behaves. The one real
gap is the silent dropped press, under tones.

### TONES THAT SAY WHAT HAPPENED
  Two outcomes are silent: a press dropped because the engine was still
  transcribing or pasting (the engine drops it; the user hears nothing),
  and a transcript captured but never pasted (no text field focused,
  elevated window). The existing high, low and double-low tones can cover
  both; no new sound, no new slider.

### X HIDES, MINIMIZE MINIMIZES
  Today minimize goes to the tray and X exits after a confirm. Convention
  is minimize to taskbar, X to tray, Exit in the menu. A Settings box
  "Close button exits the app" for anyone who wants the old way.

### SETTINGS AND THE OUTPUT WINDOW OPEN TOGETHER
  Settings can be open with no output window showing, so a dictation made
  while adjusting Settings gives no visible feedback. Opening Settings
  shows the window first; hiding the window closes Settings.

### WELCOME DIALOG ON FIRST RUN
  First run opens Settings and explains nothing. One dialog, not a chain
  of message boxes: pick a mic, bind a PTT button, maybe bind the
  output-window hotkey, then Settings opens. Only matters if a copy ever
  reaches someone with no one in the room to tell them.

## E. WHAT THE APP KEEPS
The user's control over their own recorded words. Three files hold them:
the transcript log, the dictation database and the FLAC recordings. One
Settings area, one switch and one budget serve dictation and ambient mode
alike.

### TRANSCRIPT LOG TOGGLE, AND THE DISCLOSURE
  transcript_log.txt records every dictation on every machine, gated on a
  code constant, with nothing telling the user it exists. A View-menu
  toggle gives them the control, and is also the disclosure: the only file
  under userdata/logs with the user's own words in it.

### CORPUS OPT-IN THE USER CAN SEE AND SWITCH OFF
  dev-flags.toml keeps a handed-out copy from recording, which is the right
  default and the wrong ceiling: a corpus cannot be back-filled, so a user
  who never gets the choice starts from zero the day any corpus feature
  ships. One Settings switch, disclosed in plain words at the moment it
  would start recording, off without drama.

### FLAC RETENTION, A SIZE BUDGET
  Anyone recording prunes by hand or lets the folder grow. A dropdown:
  roughly 1, 5, 10 GB or unlimited. Deletion goes by age, oldest day
  folders first, since clips are filed under YYYY/MM/DD. Rows are never
  touched. Nobody has measured how much audio voice-ID needs, and you can
  delete later but not undelete. spike-notes.md DICTATION CAPTURE RATE.

## F. BEYOND DICTATION
Modes that change what the product is. All but one need a local LLM or a
corpus that does not exist yet. The captures table already carries a mode
column and a speaker column for them.

### AMBIENT MODE
  A second mode beside push-to-talk: continuous capture in five-minute
  FLAC chunks, transcribed in the background, written to a timestamped
  day log, never typed anywhere. Silence skipped before Whisper sees it.
  Then speaker attribution in three tiers, each shippable alone: plain
  text; Speaker A/B labels; persistent voice IDs with a table the user
  names one row at a time. Then lookup by person and day. Validate with
  the mic listening to a video playing out loud, a different one from
  the same channel each session.

### VOICE PROMPT MODE
  A second trigger marks speech as a prompt to a local model rather than
  text to type. Decide first which it is: generate at the cursor,
  transform a selection, answer in the output window, or run a command.
  Four features, not one. Needs its own tone and a busy state.

### SELECTION TRANSFORM
  Speak at selected text and have it replaced. Cheap mechanically, since
  copy does not deselect and the app already owns copy and paste. Three
  hazards: the selection can die mid-sentence, the paste replaces whatever
  is selected at paste time, and an empty selection transforms a stale
  clipboard. This edits documents; a bug destroys work.

### SEARCH BY MEANING
  Ask a question and get back what you said about it months ago, from a
  corpus that never left the machine. Embeddings in SQLite, a local LLM
  reading the matches. The hard part is not storage but the retrievable
  unit: a seven-second utterance means nothing alone. Pick the embedding
  model late: vectors from two models do not share a space, so a change
  discards every vector stored. Vectorize in a background batch, never on
  the dictation path. On an 8 GB card Whisper and the model take turns.
  sqlite-vec loads here; see spike-notes.md.
