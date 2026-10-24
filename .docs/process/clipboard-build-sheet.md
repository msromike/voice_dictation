# Build sheet: clipboard fix, then the paste-last hotkey

Written 2026-10-24 on Fable for Opus to run, with Mike at the keyboard.
Read `.docs/agent-rules.md` first. Then this file, top to bottom. Tick boxes
as you go; MIKE lines are his to do, everything else is yours.

The project is frozen. This sheet is the ONE code change Mike authorized,
in two commits: the clipboard fix (Steps 0-7), then an optional hotkey
(Step 8). Nothing else in the code moves. No tidying, no deleting dead
code, no drains. Memory rules that bind: restart-before-commit (you load
it, Mike exits and relaunches and confirms, then commit),
show-before-delete, measured facts go to spike-notes.txt in the same
commit, never start the app yourself. Spike scripts live in your scratchpad
directory, never in the repo.

## Context

Every dictation destroys the clipboard. `KeyboardInjector.inject()` in
`voice-dictation/vdict/daemon/keyboard.py` saves the clipboard with
pyperclip (text only), pastes with Ctrl+V, sleeps 50 ms, and restores only
when `preserve_clipboard` is False. Mike's config.json has it True, the
default in `KeyboardConfig` (`voice-dictation/vdict/common/config.py`) is
True, so the restore never runs for anyone. The name is inverted: True
means "leave the dictated text there".

Goal: after a dictation, whatever was on the clipboard before is back.
Text, images, rich text, and files from Explorer if Spike 1 says they
round-trip. This is backlog.txt B6's DELIVERY and FORMAT HANDLING only.
B6's PTT gating and tone changes do NOT ship; they stay in backlog.txt.

Design, the one clipboard managers use: snapshot every format with
win32clipboard (pywin32, already installed), put the text on the clipboard
with Windows' history-exclusion flag so Win+V doesn't record every
dictation, Ctrl+V as today, wait a measured fixed delay, write every format
back in the original order. No WM_RENDERFORMAT in production. The three
spikes measure what nobody has measured: which formats round-trip, whether
the exclusion flag works, how long a paste takes to land.

When a paste doesn't land (nothing focused, elevated window), the old
clipboard comes back after the delay anyway and the dictation is in the
output window. Mike's recovery is what it is today: hotkey, raise the
window, copy from there. Step 8 turns that into one keystroke.

## Files

- `voice-dictation/vdict/daemon/keyboard.py` -- `KeyboardInjector` rewrite
- `voice-dictation/vdict/common/config.py` -- delete `KeyboardConfig`
- `voice-dictation/vdict_daemon.py` -- drop the `preserve_clipboard=` arg
  where `KeyboardInjector` is built
- `requirements.txt` -- drop `pyperclip` (keyboard.py is its only importer)
- `README.md` -- Known limitations "It replaces your clipboard", How it works
- `CHANGELOG.md` -- Unreleased / Fixed
- `.docs/process/spike-notes.txt` -- new section with the measurements
- `.docs/process/backlog.txt` B6 and `new_next.md` item 3 -- one-line
  pointer each

## Step 0: housekeeping

- [ ] Append to memory `frozen-means-no-code-changes.md`: this sheet is the
      one exception Mike authorized on 2026-10-24.
- [ ] `git status` shows nothing but this sheet (uncommitted if Mike did not
      commit it), at c6329bc or later. Anything else: stop and report.
- [ ] MIKE: is Windows clipboard history on? Settings > System > Clipboard >
      "Clipboard history". Say on or off. Spike 2 needs to know.

## Spike 1: which formats round-trip (script, no app change)

Script `clip_roundtrip.py` in the scratchpad. It:

1. Opens the clipboard (retry 5 x 20 ms on failure), walks
   `EnumClipboardFormats` from 0, collects `(format_id, GetClipboardFormatName
   or the CF_ constant name)` in order.
2. For each format, tries `GetClipboardData(fmt)`. Records: ok + python type
   + length, or the exception text.
3. Closes. Prints the table.
4. With `--restore`: empties the clipboard, writes a marker text, then writes
   back every format that read OK, in the original order, skipping GDI-handle
   formats (CF_BITMAP 2, CF_METAFILEPICT 3, CF_PALETTE 9, CF_ENHMETAFILE 14,
   CF_OWNERDISPLAY 0x80, CF_DSPBITMAP 0x82, CF_DSPMETAFILEPICT 0x83,
   CF_DSPENHMETAFILE 0x8E). Then re-enumerates and prints the after table
   next to the before, with a byte-equality column.

UNVERIFIED and settled by this spike: what pywin32's `GetClipboardData`
returns per format (str for text, tuple for CF_HDROP, bytes for HGLOBAL
formats, raises or int for GDI handles); whether Windows re-synthesizes
CF_BITMAP from a restored CF_DIB; whether "DataObject", "Ole Private Data"
and similar OLE formats restore without breaking the paste.

- [ ] Write the script. Run it on whatever is on the clipboard now, read
      mode only. Fix script errors.
- [ ] MIKE: copy a sentence in Notepad. You run `--restore`. MIKE pastes in
      Notepad: same sentence?
- [ ] MIKE: Win+Shift+S a screenshot (or copy an image in Paint). You run
      `--restore`. MIKE pastes into Paint: image intact?
- [ ] MIKE: copy a formatted paragraph from a browser page. You run
      `--restore`. MIKE pastes into Word or WordPad and into Notepad: both
      look like before?
- [ ] MIKE: in Explorer, Ctrl+C one file. You run `--restore`. MIKE Ctrl+V
      in another folder: does the file copy? If not, CF_HDROP needs the
      DROPFILES struct rebuilt (20-byte header: pFiles=20, pt=0,0, fNC=0,
      fWide=1; then each path UTF-16LE null-terminated; then one more
      null). Try it once. If it still fails, CF_HDROP joins the skip list
      and a `log("note", ...)` names it on restore.
- [ ] Record per format: round-trips / skip / rebuild. The skip set becomes
      a module constant in keyboard.py with the measured reason beside it.

## Spike 2: history exclusion flag (script)

- [ ] Script `clip_exclude.py`: `fmt = RegisterClipboardFormat(
      "ExcludeClipboardContentFromMonitorProcessing")`; open, empty,
      `SetClipboardText("vdict exclude test")`, `SetClipboardData(fmt,
      b"\0\0\0\0")`, close.
- [ ] MIKE (history on): run it, press Win+V. Is "vdict exclude test" in the
      list? Expected: no. If it IS there, try the other flag,
      "CanIncludeInClipboardHistory" with a 4-byte zero DWORD, and retest.
      If history is off, record "not testable here" and keep the flag; it's
      harmless.
- [ ] Record the result.

## Spike 3: how long until the paste lands (script, measures the delay)

The only way to pick the restore delay from a number instead of a guess.
Production does NOT use this mechanism. Rules from backlog.txt B6 "RULES
THAT ARE EASY TO GET WRONG" apply: never OpenClipboard inside the
WM_RENDERFORMAT handler; keep the handler short; WM_RENDERFORMAT is sent
directly to the owner window, so a hidden window is enough.

- [ ] Script `clip_render_timing.py`: win32gui window class with a WndProc
      handling WM_RENDERFORMAT (serve "vdict timing test " via
      `SetClipboardData(CF_UNICODETEXT, ...)`, no OpenClipboard, and record
      `time.perf_counter()`), WM_RENDERALLFORMATS (open, serve, close),
      WM_DESTROYCLIPBOARD (ignore). Main: create window, open clipboard,
      empty, `SetClipboardData(CF_UNICODETEXT, None)` plus the exclusion
      flag from Spike 2 (so Win+V history doesn't trigger the render
      first), close, countdown 3 s printed so MIKE can focus the target,
      `pyautogui.hotkey('ctrl','v')`, pump messages up to 3 s, print
      t_render - t_hotkey in ms, or TIMEOUT.
- [ ] MIKE focuses each target before the countdown ends; you run once per
      target, three runs each: Notepad, VS Code editor, Chrome/Edge address
      bar, Windows Terminal, the app Mike dictates into most.
- [ ] One run with nothing focused on a text field (desktop) and one into an
      elevated window if Mike has one open: expect TIMEOUT. That confirms
      the no-landing case behaves as the Context says.
- [ ] Record all numbers. RESTORE_DELAY = max measured landed-time x 3,
      rounded up to the next 50 ms, floor 150 ms. If the spike fights back
      for more than 30 minutes, stop: RESTORE_DELAY = 300 ms, marked
      UNVERIFIED.

## Step 4: the code change

- [ ] `keyboard.py`, `KeyboardInjector`:
  - imports: `win32clipboard`, `win32con`; `pyperclip` gone; `pyautogui`
    and `time` stay. Drop the ImportError wrapper; crash-fast, deps are
    installed.
  - module constants: `RESTORE_DELAY` (from Spike 3, with the measurement
    in the comment), `_SKIP_FORMATS` (from Spike 1, reasons beside),
    `_EXCLUDE_FMT = RegisterClipboardFormat(...)` (from Spike 2).
  - `_open_clipboard()`: `OpenClipboard()` with 5 x 20 ms retry on
    `pywintypes.error`; returns False if it never opens.
  - `_snapshot()`: open; enumerate in order; for each fmt not in skip,
    `GetClipboardData` in try/except -- a format that fails to read is
    skipped, not fatal; close; return the ordered list of (fmt, data).
    Open failure: `log("note", "Clipboard busy -- not restored this
    time.")`, return None.
  - `_restore(items)`: open; `EmptyClipboard`; `SetClipboardData(fmt, data)`
    for each, in order, each in its own try/except that logs the format
    name on failure and continues; close. CF_HDROP rebuilt per Spike 1 if
    it round-tripped, else skipped.
  - `inject(text)`: empty-text guard as today; `items = _snapshot()`; open;
    empty; `SetClipboardText(text + " ", CF_UNICODETEXT)`;
    `SetClipboardData(_EXCLUDE_FMT, b"\0\0\0\0")`; close;
    `pyautogui.hotkey('ctrl','v')`; `time.sleep(RESTORE_DELAY)`;
    `if items is not None: _restore(items)`.
  - `__init__` takes no args. Docstrings two lines max.
- [ ] `config.py`: delete `KeyboardConfig` and the `keyboard:` field on
      `Config`. pydantic ignores the stale `"keyboard"` block in Mike's
      config.json (no `extra="forbid"` anywhere), and the next Settings
      save rewrites the file without it.
- [ ] `vdict_daemon.py`: `keyboard = KeyboardInjector()`.
- [ ] `requirements.txt`: remove `pyperclip`. Grep first; keyboard.py is the
      only importer as of c6329bc. Do NOT uninstall it from the global
      Python.
- [ ] `python -c "import sys; sys.path.insert(0,'voice-dictation'); import
      vdict.daemon.keyboard, vdict.common.config"` loads clean.
- [ ] `python -m ruff check .` and `python -m pyright` clean before asking
      Mike to restart. Report the numbers.

## Step 5: Mike tests the real app

- [ ] MIKE: tray > Exit, relaunch from the Desktop shortcut, wait for the
      double beep. Session block shows in the output window.
- [ ] MIKE, each in turn, saying pass/fail:
  - Copy a sentence. Dictate into Notepad. Ctrl+V: the sentence comes back.
  - Screenshot to clipboard. Dictate. Paste into Paint: image comes back.
  - Copy a formatted browser paragraph. Dictate. Paste into Word:
    formatting comes back.
  - Copy a file in Explorer. Dictate. Ctrl+V in a folder: file copies (or
    the note appears in the output window, if CF_HDROP was skipped).
  - Press Win+V: no dictated sentences in the history list.
  - Dictate into the app Mike uses most: the dictated text lands, not the
    old clipboard. Three times.
  - Dictate with focus on the desktop (no text field): nothing pastes.
    After the delay the old clipboard is restored anyway, so Ctrl+V in
    Notepad gives the OLD clipboard. MIKE then does what he does today:
    hotkey to raise the output window, copy the dictation from there,
    paste it. Confirm that works.
- [ ] Any fail: fix, repeat Step 4's lint line, MIKE restarts again. One
      change at a time.

## Step 6: docs, in the same commit

- [ ] `spike-notes.txt`, new section `CLIPBOARD ROUND-TRIP (B6)`: Spike 1's
      per-format table, Spike 2's result, Spike 3's timings per target and
      the RESTORE_DELAY derived from them. MEASURED / UNVERIFIED as
      agent-rules.md defines them.
- [ ] `README.md`: Known limitations -- replace the "It replaces your
      clipboard" paragraph with what's true now: the clipboard comes back
      after each dictation; when a paste doesn't land (no text field
      focused, or an elevated window) the dictation is in the output
      window, raise it with the hotkey and copy from there; files from
      Explorer, if Spike 1 skipped CF_HDROP. How it works -- the "Its
      drawbacks are in Known Limitations above" sentence goes.
- [ ] `CHANGELOG.md` Unreleased > Fixed: one entry, user language.
- [ ] `backlog.txt` B6: one line under the heading: "DELIVERY and FORMAT
      HANDLING shipped <sha>, fixed measured delay instead of
      WM_RENDERFORMAT; measurements in spike-notes.txt CLIPBOARD
      ROUND-TRIP. PTT GATING and TONES remain." Nothing else in B6 moves.
- [ ] `new_next.md` item 3: same one line. Nothing else moves.

## Step 7: commit and the stick

- [ ] "commit per protocol". `fix:` header. Report lint numbers, vulture
      findings, complexity numbers as the protocol says. This sheet goes in
      the commit with its boxes ticked.
- [ ] If G: is still plugged in: `git archive --format=zip -o
      G:\voice_dictation.zip <new sha>`, list the zip to confirm no
      userdata/dev-flags, and tell Mike the stick is current. If G: is
      gone, tell Mike the stick holds c6329bc and needs the one-line
      re-archive before he goes.

## Verification, Steps 0-7

Done = Step 5 all pass with Mike watching, commit exists, spike-notes
carries the numbers, README no longer says the clipboard is destroyed. Say
DONE only then. Anything short of it is NOT DONE with the failing line
named. Step 8 is separate: skipping it leaves Steps 0-7 DONE.

## Step 8 (polish, own commit): hotkey that pastes the last dictation

Only after Step 7's commit exists. Mike decides at that point whether
tonight has room for it. It leans on the new `inject()`; nothing here
touches the daemon.

Why: when a paste doesn't land, or lands in the wrong window, Mike today
raises the output window, selects, copies, clicks back, pastes. This is one
keystroke instead: a second global hotkey, bound in Settings, unset by
default, that pastes the last transcript wherever the cursor is.

The pieces already exist:

- the tray sees every transcript line in `vdict/tray/console.py`'s drain
  loop, where `category == "transcript"` feeds `transcript.write`
- the output-window hotkey is registered by `vdict/tray/hotkey.py`,
  captured by `vdict/tray/hotkey_capture.py`, wired in `vdict/tray/app.py`
  (`_register_hotkey`, `_on_hotkey`, `_raise_window`), with its Settings
  row `_build_hotkey_row` in `vdict/tray/settings.py` and its session-block
  line `_hotkey_line` in `vdict/tray/session.py`
- the paste is `KeyboardInjector().inject(text)` from Step 4

What has to change: hotkey.py holds exactly ONE hotkey today
(`_HOTKEY_ID = 1`, one `_callback`, one `_registered`). It needs two.

- [ ] `hotkey.py`: key everything by id. `register(hotkey_id, mods, vk,
      callback)` and `unregister(hotkey_id)`; `_callbacks: dict[int,
      callable]`, `_registered: set[int]`. The pump dispatches
      `_callbacks[msg[2]]()` -- WM_HOTKEY's wParam is the id. `_claim` and
      `_release` take the id. Two module constants: `OUTPUT_WINDOW = 1`,
      `PASTE_LAST = 2`. The `_command` reply protocol has to carry the id;
      pick the way with fewer lines and say which.
- [ ] `config.py`: `paste_hotkey: HotkeyConfig = HotkeyConfig()` on
      `Config`, beside `hotkey`. `FIELD_LABELS` gets its three locs with
      the label "Paste-last hotkey".
- [ ] `settings.py`: `_build_hotkey_row(parent, label, field)` takes the
      label text and which config field; called twice ("Output Window
      Hotkey:" / `hotkey`, "Paste Last Dictation Hotkey:" /
      `paste_hotkey`). `save()` sets both. `_rebind_on_close` unregisters
      and re-registers both. Refuse the same combination on both rows:
      after capture, if the two bindings match, `messagebox.showwarning`
      and restore the second.
- [ ] `hotkey_capture.py`: `capture()` unregisters ONLY the hotkey being
      rebound, so it needs the id -- pass it through from the row. The
      `_confirm_bare_key` text says "will raise this window"; make the verb
      a parameter ("raise this window" / "paste your last dictation").
- [ ] `console.py`: in the drain, `if category == "transcript":
      self.last_transcript = text`, before the `transcript.ENABLED` check
      (the paste hotkey works whether or not the transcript log is on).
      Initialize `self.last_transcript = None` in `__init__`.
- [ ] `app.py`: `_register_hotkeys(config)` registers both and records
      name/failed for both. `_on_paste_hotkey` runs on hotkey.py's thread,
      which is fine for clipboard and pyautogui (no Tk):
      1. `text = self.console.last_transcript`; if None, `log("note",
         "Nothing dictated yet -- nothing to paste.")` and return.
      2. Wait for Mike's fingers to leave the keys: poll
         `vdict.daemon.keyboard._modifier_held()` (also check VK_LWIN and
         VK_RWIN) every 10 ms, up to 1 s. Without this the synthetic Ctrl+V
         arrives as Ctrl+Shift+V or Ctrl+Alt+V and the target does
         something else. If still held after 1 s, paste anyway and log a
         note.
      3. `KeyboardInjector().inject(text)`. One injector instance held on
         the App, not built per press.
      4. `log("note", f"{name} pasted the last dictation")`.
- [ ] `session.py`: `log_session_block` gets the second hotkey's name and
      failed flag; a second "Paste hotkey" line with the same unset /
      taken / set wording, verb "pastes your last dictation anywhere".
- [ ] Lint clean (ruff, pyright). Report numbers.
- [ ] MIKE: Exit, relaunch, double beep. Settings: bind the new hotkey.
      NOT Ctrl+Shift+V -- Chrome, VS Code and Windows Terminal use it.
      Ctrl+Alt+V or a spare F-key. Save & Restart. Session block shows
      both hotkey lines.
- [ ] MIKE tests, pass/fail each:
  - Dictate into Notepad. Click into Word. Press the hotkey: same text
    appears. Ctrl+V afterwards: the pre-dictation clipboard, not the text.
  - Dictate with nothing focused. Click into Notepad. Hotkey: text
    appears.
  - Hold the hotkey keys down for a full second before releasing: text
    still appears exactly once.
  - Fresh launch, no dictation yet, hotkey: the "Nothing dictated yet"
    note in the output window, nothing pasted.
  - Output-window hotkey still raises the window. Both unbound and rebound
    once through Settings without the app needing a relaunch.
- [ ] `README.md`: Settings table row "Paste Last Dictation Hotkey"; one
      paragraph under "Using it" after the tray-icon section: when a
      dictation lands nowhere, press it in the window you meant.
      CHANGELOG Unreleased > Added.
- [ ] "commit per protocol", `feat:` header, own commit. Re-archive to G:
      as in Step 7 if the stick is there.

Delete this sheet in the commit that ticks its last box, Step 7's if
Step 8 is skipped, Step 8's otherwise. The measurements live on in
spike-notes.txt; the decisions live on in the commit messages.
