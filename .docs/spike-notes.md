# Spike Notes

Things that were measured and would be measured again by anyone who did not
know. Each section says what it decided in the code or the backlog.

## WHISPER HALLUCINATES ON SHORT REAL CLIPS

Clips of 140-180 ms of real mic audio can come back as confident false text
("Let's go.", "Thank you."). Synthetic silence or noise of the same length
does not do it; only real transients. That is why MIN_RECORDING_SAMPLES in
vdict_daemon.py is 6400 (0.4 s): it filters exactly that range.

transcribe() takes 190-200 ms whether the clip is 10 ms or 2 s, after a
one-time 500-700 ms warm-up on the first call. Two concurrent calls on one
model serialize, no speedup.

## DISPLAY DPI (Windows, Tk)

A process that has not declared DPI awareness reads the system DPI as 96,
whatever the display is set to, and Tk's own figures say ~96 there too. So
a probe must run under the same awareness as the app or its number is
fiction. With awareness set, Windows and Tk still disagree by a hair (168
vs 167.876); vdict/tray/dpi.py reads Windows through ctypes so nothing
depends on a live Tk root.

## TONES CLICK FOR TWO REASONS (sounddevice/WASAPI)

sd.play() opens a new WASAPI stream per call, and the open is an audible
click. One persistent sd.OutputStream written repeatedly has none, which is
why vdict_daemon.py holds one open for the whole process. The second cause
is a waveform ending on a non-zero sample, which the driver plays as a
step; audible only on a good chain, masked on cheap speakers, so a no-click
result on cheap equipment is not evidence. A cosine fade over the last 1 ms
removes it; the shipped WAVs' fade stops ~0.05% short of zero, worth fixing
whenever they are regenerated.

WASAPI auto_convert resamples a 192 kHz source to a 48 kHz device correctly.
A crashed process does not lock the output device; Windows reclaims it.

Still unexplained: a brief burst of white noise right after a tone, which
feeding the stream continuous silence did not cure. Underrun, not
discontinuity, is the leading theory. Not confirmed.

## DICTATION CAPTURE RATE

Roughly 570 clips a day on this machine, swinging 120 to 956: about 208,000
captures a year, tens of megabytes of rows and roughly 34 GB of FLAC.
Re-derive from the captures table or the FLAC folder over a known span; it is
one person's habit. Rows are permanent at that size; audio is the only store
worth rotating, and nobody has measured how much of it voice-ID needs.

## VOCABULARY

initial_prompt is a per-call argument to STTEngine.transcribe(), not baked
into the model, so reading vocabulary.txt on every dictation is cheap:
measured 2026-09-30, a real 581-byte file reads in 0.13 ms median, 0.41 max
over 1000 reads; with 500 office words added, 0.28 median, 0.63 max.

Only the last 223 prompt tokens reach Whisper: faster_whisper keeps
previous_tokens[-(max_length // 2 - 1):] with max_length 448. 500 words
encode to 1055 tokens with large-v3, so the first ~400 are dropped silently.

A bare word does nothing; phrases work. Mike dictated the same ten lines
per round, eight containing Claude where the corpus shows "clod" and
"cloud", two real clouds, app relaunched between rounds. Empty vocabulary 5
of 8; "Claude" 5 of 8; "Claude, CLAUDE.md, Claude Code" 8 of 8, with both
clouds left alone. Write vocabulary entries as spoken phrases.

## WHISPERMODEL SWAP RELEASES CUDA MEMORY

Four cycles of load small/float16, transcribe, del, gc: each load +808 MiB,
each delete back to +165 MiB over baseline, no drift. The 165 MiB is the
CUDA context, paid once per process. Reload in place is safe, which is what
Settings does since a035ee4.

## PUNCTUATION RESTORATION

rpunct is a dead end: it hard-pins 2021 pandas and torch with no Python
3.12 wheels. deepmultilingualpunctuation (fullstop-punctuation-multilang-
large), CPU only: ~3 s load, ~88 ms per call. At an untuned 25-words-per-
sentence threshold, 52 real transcript lines flagged only one; HOLD mode's
release between thoughts may already prevent the run-ons this targets.

## PHONETIC CODES COLLIDE ON ORDINARY WORDS

jellyfish (maintained, MIT, Rust-backed) gives metaphone, soundex, nysiis
and match_rating_codex. "Trey" and "Tray" share a metaphone code, so the
mechanism works for the motivating case. Bare code equality is not safe:
"cloud" and "clod" both collide with "Claude", "true" with "Tray", "pity"
with "PTT". A bare match rewrites an everyday word to a name.

## OTHER ENGINES TRIED, 2026-10-22 -- FASTER-WHISPER STAYS (Mike's ruling)

Cactus Whistle (16.9 MB, CPU only), 40 random dictations scored against the
app's large-v3 GPU text: 9.6 errors per 100 words at 0.75 s per clip;
base.en 4.6 at 0.69 s; small.en 3.4 at 2.02 s. Its "beats Whisper" claim is
against multilingual base only.

IBM Granite Speech 4.1 2B (bf16, transformers, throwaway venv): load 8.4 s,
4555 MiB of GPU, 0.20 s per second of audio against large-v3's 0.11. Ten
random dictations: seven identical, three one-word splits. Mike: minimal to
zero gain. Reopens only if a later engine shows a clear gap on his own
audio; a leaderboard is not that evidence. Both setups were deleted.

## WHISPER MODEL LADDER (Mike's GPU testing, i7 9th gen + 3070 Ti)

GPU, VRAM watched live: small.en / medium.en / large-v3, one per card tier
(4 GB+ / 6 GB+ / 8 GB+), biggest that fits. large-v3-turbo is an alternate,
not a fourth tier. CPU, by reasoning not measurement: tiny.en / small.en /
medium.en. Turbo on CPU costs about what large-v3 costs, because its pruning
is in the decoder and CPU struggles with the encoder. distil-small.en
rejected as a tradeoff to explain for marginal gain. Per-tier speed on real
hardware is unverified.

## CAPTURE LENGTH

Over the corpus as of 2026-09-30: median capture 7.3 seconds, 85 percent
under fifteen. Utterances, not documents.

## MICROPHONE DEVICES (sounddevice/PortAudio/WASAPI)

Read from PortAudio's and sounddevice's source (github.com/PortAudio/portaudio,
github.com/spatialaudio/python-sounddevice), then confirmed on real
hardware: PDP mic, a Behringer mixer input, a webcam mic, all through
vdict/daemon/portaudio_io.py.

  - Pa_Initialize's WASAPI backend does a fresh IMMDeviceEnumerator query
    every call -- reinit sees whatever is connected now, not a cached
    answer. CONFIRMED: the mixer appeared and disappeared correctly across
    enable/disable cycles. reinit latency 0.02-0.03 s over 5 runs.
  - A failed stream never says why. Sixteen WASAPI failure paths collapse
    into one generic thread-death signal; PortAudio's real-time callback
    contract forbids the slow work needed to preserve which one occurred.
    CONFIRMED: stream.active goes False on its own when the device
    disappears mid-stream, no exception, no status flag. That flag is the
    only detection signal there is.
  - A failed open or start always raises PortAudioError, whatever the
    cause, including another app holding the device in WASAPI exclusive
    mode. Traced through sounddevice's single _check() and CONFIRMED with
    a real exclusive-mode hog process.
  - Pa_Initialize/Pa_Terminate must be called from the same thread (COM
    apartment affinity; get it wrong and cleanup silently leaks). sounddevice
    auto-initializes on import, on whatever thread imports it first.
    SOURCE-ONLY, never tested: no tooling here isolates a silent leak.
  - Three devices enabled at once each resolved to the right index by
    name, no cross-matching.
  - Windows' default input does not reflect user intent: the webcam
    promoted itself to Default Device unprompted, twice.

## LIBRARY GAPS

Hand-rolled because a library did not do it; the code says why at the
site. Read before "simplifying" either.

  - settings.py _has_cuda and stt.py PATH prepend: ctranslate2's own
    add_dll_directory covers ROCm only, not the nvidia pip wheels; the
    PATH prepend is the fix, done ONCE at import by the module that loads
    ctranslate2 first, not twice.
  - config.py _delete_at_path: pydantic validates whole or fails whole; no
    per-field fallback to default exists (model_validate takes no such
    option), so the per-field repair is hand-rolled.

## CLIPBOARD ROUND-TRIP AND DELIVERY (keyboard.py, 2026-10-24)

Format round-trip through win32clipboard, EnumClipboardFormats order kept:

  MEASURED text: CF_UNICODETEXT, CF_TEXT, CF_OEMTEXT, CF_LOCALE all
  byte-identical after a save/replace/restore cycle.

  MEASURED image: CF_DIB, CF_DIBV5, DataObject, Ole Private Data and
  System.Drawing.Bitmap byte-identical. CF_BITMAP cannot be written back --
  GetClipboardData returns a GDI handle, not bytes -- but Windows
  re-synthesizes it from the restored CF_DIB and it reappears in the
  enumeration, so skipping it loses nothing.

  MEASURED rich text: HTML Format, Rich Text Format and the text formats
  byte-identical.

  MEASURED CF_HDROP: reads back as a tuple of paths, so SetClipboardData
  raises TypeError on it. Rebuilding the DROPFILES struct restores it --
  20-byte header (pFiles=20, pt 0,0, fNC=0, fWide=1), then each path UTF-16LE
  null-terminated, then one more null. Windows' own GetFileDropList read the
  restored path back correctly.

  Skip set, all GDI handles: CF_BITMAP 2, CF_METAFILEPICT 3, CF_PALETTE 9,
  CF_ENHMETAFILE 14, CF_OWNERDISPLAY 0x80, CF_DSPBITMAP 0x82,
  CF_DSPMETAFILEPICT 0x83, CF_DSPENHMETAFILE 0x8E.

History exclusion:

  MEASURED: RegisterClipboardFormat("ExcludeClipboardContentFromMonitor-
  Processing") returned 49987 here; written with four zero bytes. A control
  string written without the flag appeared in Win+V, the string written with
  it did not. Clipboard history was on
  (HKCU\Software\Microsoft\Clipboard, EnableClipboardHistory = 1).
  It matters more than it looks: the history monitor asks for the text the
  instant it is announced, which would fire the delivery receipt before any
  paste happened.

Delivery -- why there is no delay constant:

  MEASURED: announcing CF_UNICODETEXT as a null handle (delayed rendering)
  and sending Ctrl+V, Notepad asked for the text 6.0 / 6.3 / 6.5 ms later,
  3 runs of 3. WM_RENDERFORMAT arriving is proof the paste landed, so the
  restore waits on an event and not on a guess about machine speed.

  MEASURED: an earlier run of the same spike read 103.7 / 103.9 / 104.0 ms.
  That was pyautogui's default 0.1s PAUSE delaying hotkey()'s return, and
  with it the message pump -- not the paste. keyboard.py sets
  pyautogui.PAUSE = 0.

  MEASURED: the whole inject() -- snapshot, announce, paste, receipt,
  restore -- returned in 16.8 ms with an image on the clipboard, and the
  image was intact afterwards.

  _RECEIPT_TIMEOUT = 1.0s is a backstop for "nobody ever asked" (no text
  field focused, elevated window). Being wrong about it delays a restore;
  it cannot cause a wrong paste, which is exactly what a fixed delay can.

  CONFIRMED IN THE APP 2026-10-24, Mike at the keyboard: clipboard sentence
  survives a dictation, screenshot survives a dictation, dictations land
  where he is typing, and Win+V lists no dictations.

  UNVERIFIED: no target other than Notepad was timed, and the numbers above
  are from one machine. The design does not depend on either.

Clipboard owner on its own thread (keyboard.py, 2026-10-25):

  MEASURED: after _restore the hidden window owns the clipboard. With that
  window's thread not pumping, another process's EmptyClipboard took
  5003.6 / 5007.7 / 5011.2 ms -- Windows gives up on WM_DESTROYCLIPBOARD
  after 5 s -- and the owner never saw the message. a8f7255's main loop did
  not pump between captures, so after any dictation the next copy in any
  app stalled that app 5 s (5003.6 ms with a8f7255's KeyboardInjector).
  With the owner idling in MsgWaitForMultipleObjects([wake], INFINITE,
  QS_ALLINPUT) and pumping on wake, the same copy took 0.2 ms and the
  owner saw WM_DESTROYCLIPBOARD.

  MEASURED: WM_RENDERFORMAT reaches an owner waiting in
  MsgWaitForMultipleObjects([], ms, QS_ALLINPUT) -- pywin32 accepts the
  empty handle list -- from a reader on another thread of the same process
  and from another process alike, 0.7 ms each, the same as the
  PumpWaitingMessages + sleep(0.001) poll it replaces.

  MEASURED, Win32 EDIT control as target: inject() from a non-owner thread
  107 ms on the first call; 100 paste_async in a burst landed 99 in
  11.65 s; receipt wait median 0.5 ms; one paste hit the 1 s backstop and
  did not land. UNVERIFIED why: the likeliest is the EDIT's single
  OpenClipboard colliding with a clipboard listener woken by the previous
  restore, which a8f7255 would lose the same way. Shift held (injected)
  before a paste was up after it, and the paste landed.

  MEASURED: a Tk Text widget fires <<Paste>> on the fake Ctrl+V but never
  sends WM_RENDERFORMAT, so delayed-rendered text does not land in Tk. The
  app has no Tk paste target; test scripts use an EDIT control instead.

Modifiers around the fake Ctrl+V (keyboard.py, 2026-10-25, after Step 6):

  CONFIRMED IN THE APP, Mike at the keyboard: with the one-way fake Shift
  release, holding Ctrl+Shift and tapping V typed "vvvvvvvv" after the
  first paste. The fake Ctrl+V's trailing Ctrl key-up had told Windows
  Ctrl was up as well, so the following taps were bare letters.

  Built instead: the keyboard hook records physical modifier state from
  non-injected events (_track_modifier); _send_ctrl_v lifts the modifiers
  that would change Ctrl+V's meaning, presses Ctrl only if it is not held,
  sends V, and puts back what is still physically down. MEASURED, recorded
  pyautogui calls: Ctrl+Shift held -> up shiftleft, press v, down
  shiftleft; nothing held -> down ctrl, press v, up ctrl; Shift lifted
  mid-paste -> not put back. Hook ignores an injected Shift key-up and
  tracks WM_SYSKEYDOWN. Same EDIT burst on this build: 100 of 100 landed
  in 10.8 s, receipt median 0.4 ms, max 2.4 ms, clipboard text identical
  before and after.

  UNVERIFIED by script, by design: a physical key cannot be injected, so
  the hook -> set -> lift -> restore path end to end is Step 6 Test 4.

Three threads, one stdout (output.py, 2026-10-25):

  CONFIRMED IN THE APP: the output window showed
  "[NOTE] Nothing dictated yet -- nothing to paste.ready|Voice Dictation
  v1.0.0 READY" as one line, then blank lines, then a dot a second for the
  rest of the session. The pipe-reader thread and the main thread printed
  at the same instant; print() is two writes (text, then newline), so the
  READY line landed inside the note. The console clears its loading state
  only on a clean "ready" category (console.py drain), so the loading dots
  never stopped. Fix: log() takes a lock and makes one write.

Restore refused with "handle is invalid" (keyboard.py _restore, 2026-10-25):

  CONFIRMED IN THE APP, once: after copying a word in Windows 11 Notepad
  and dictating into VS Code's chat box, formats 13, 1 and 7 all failed
  to restore with (6, 'SetClipboardData', 'The handle is invalid.'); the
  copied word was lost. 16 (CF_LOCALE) was not reported.

  MEASURED, not reproduced: 30 cycles each of a plain owner and a
  delayed-render owner in another process, pasting into a Win32 EDIT
  control; then the same 60 into a Chromium textarea (Edge app mode).
  120 restores, every clipboard text intact, no note. str for 13 and bytes
  for 1 and 7 both write fine from the clipboard thread.

  UNVERIFIED cause. The restore path is a8f7255's, moved to the clipboard
  thread. The note now carries the data type and length and whether the
  clipboard owner at restore time was still our window.
