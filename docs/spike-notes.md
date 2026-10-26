# Spike Notes

Things that were measured and would be measured again by anyone who did not
know. Each section says what it decided in the code or the backlog.

## WHISPER HALLUCINATES ON SHORT REAL CLIPS

Clips of 140-180 ms of real mic audio can come back as confident false text
("Let's go.", "Thank you."). Synthetic silence or noise of the same length
does not do it; only real transients. That is why MIN_RECORDING_SAMPLES in
vdict_daemon.py is 6400 (0.4 s): it filters exactly that range.

## DISPLAY DPI (Windows, Tk)

A process that has not declared DPI awareness reads the system DPI as 96
whatever the display is set to, and Tk reports ~96 there too. So a probe
must run under the same awareness as the app or its number is fiction. With
awareness set, Windows and Tk disagree by a hair (168 vs 167.876);
vdict/tray/dpi.py reads Windows through ctypes so nothing depends on Tk.

## TONES CLICK FOR TWO REASONS (sounddevice/WASAPI)

sd.play() opens a new WASAPI stream per call, and the open is an audible
click. One persistent sd.OutputStream written repeatedly has none, which is
why vdict_daemon.py holds one open for the whole process. The second cause
is a waveform ending on a non-zero sample, which the driver plays as a
step; audible only on a good chain, masked on cheap speakers, so a no-click
result on cheap equipment is not evidence. A cosine fade over the last 1 ms
removes it; the shipped WAVs' fade stops ~0.05% short of zero, worth fixing
whenever they are regenerated.

## DICTATION CAPTURE RATE

Roughly 570 clips a day on this machine, swinging 120 to 956: about 208,000
captures a year, tens of megabytes of rows and roughly 34 GB of FLAC.
Re-derive from the captures table or the FLAC folder over a known span; it is
one person's habit. Rows are permanent at that size; audio is the only store
worth rotating, and nobody has measured how much of it voice-ID needs.

## VOCABULARY

initial_prompt is a per-call argument to STTEngine.transcribe(), not baked
into the model, so reading vocabulary.txt on every dictation is cheap:
a real 581-byte file reads in 0.13 ms median, 0.41 max, over 1000 reads;
with 500 office words added, 0.28 median, 0.63 max.

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

Read from PortAudio's and sounddevice's source, then confirmed on real
hardware with a PDP mic, a Behringer mixer input and a webcam mic through
vdict/daemon/portaudio_io.py. These four decide the mic handling entry in
backlog.md.

  - Re-initializing PortAudio does a fresh device query every time, in
    0.02-0.03 s. Enumerating without it returns stale data.
  - A failed stream never says why. Sixteen WASAPI failure paths collapse
    into one signal: stream.active goes False on its own, no exception, no
    status flag. That is the only detection there is.
  - A failed open always raises PortAudioError, whatever the cause,
    including another app holding the device in exclusive mode.
  - Windows' default input does not reflect user intent: the webcam
    promoted itself to Default Device unprompted, twice.

## SQLITE-VEC LOADS

sqlite3.enable_load_extension is present and sqlite-vec loads under this
machine's Python 3.12.10 with SQLite 3.49.1. A Python build without
extension loading would need a different mechanism for search by meaning;
check before relying on it under any other Python. At the measured capture rate,
two years is well under half a million vectors, small enough that scanning
every one beats indexing.

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

## CLIPBOARD ROUND-TRIP AND DELIVERY (keyboard.py)

Every line here is a constant or a design choice in keyboard.py.

Formats. Text, rich text (HTML Format, Rich Text Format) and image formats
(CF_DIB, CF_DIBV5, DataObject, Ole Private Data, System.Drawing.Bitmap) all
round-trip byte-identical through win32clipboard when written back in
EnumClipboardFormats order. The GDI-handle formats cannot be written back
and are _SKIP_FORMATS; CF_BITMAP among them costs nothing, because Windows
re-synthesizes it from the restored CF_DIB. CF_HDROP reads back as a tuple
of paths and must be rebuilt as a DROPFILES struct (20-byte header, paths
UTF-16LE null-terminated, one more null), which _dropfiles does.

History exclusion. Writing the ExcludeClipboardContentFromMonitorProcessing
format with four zero bytes keeps the dictation out of Win+V. It matters
more than it looks: the history monitor asks for the text the instant it
is announced, which would fire the delivery receipt before any paste.

Receipt, not delay. The text is announced with a null handle (delayed
rendering) and Ctrl+V is sent; the target asks for it 6-7 ms later, and
that WM_RENDERFORMAT is proof the paste landed, so the restore waits on an
event rather than a guess about machine speed. _RECEIPT_TIMEOUT of 1 s is
the backstop for nobody asking (no text field, elevated window); being
wrong about it delays a restore and cannot cause a wrong paste. pyautogui
PAUSE must be 0 or its default 0.1 s delays the message pump and the
receipt reads 100 ms.

The owner must pump. After a restore the hidden window owns the clipboard,
and if its thread is not pumping messages, the next copy in any app stalls
that app 5 s while Windows waits for WM_DESTROYCLIPBOARD. The owner idles
in MsgWaitForMultipleObjects and wakes for any input; the same copy then
takes 0.2 ms.

Modifiers. A fake Ctrl+V that releases Ctrl at the end tells Windows the
user's physically held Ctrl is up too, so Ctrl+Shift+V held across a paste
typed "vvvvvvv". The keyboard hook records physical modifier state from
non-injected events (_track_modifier); _send_ctrl_v lifts the modifiers
that would change Ctrl+V's meaning, presses Ctrl only if it is not held,
sends V, and puts back what is still physically down.

Test targets. A Tk Text widget fires its paste event on the fake Ctrl+V but
never sends WM_RENDERFORMAT, so delayed-rendered text does not land in Tk.
Test scripts use a Win32 EDIT control or a Chromium textarea.
