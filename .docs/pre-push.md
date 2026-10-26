# Pre-Push Checklist

Run in order before the repo goes public, and again before any release tag.

GOING PUBLIC IS A FRESH REPO from a cleaned copy, never this one. This
repo's history holds config.json and the dictation database (userdata was
tracked 2026-10-24 to 2026-10-25). The public repo is the code and what a
user needs to run it. Nothing else.

  SHIPS      voice-dictation/, tools/check_docstrings.py, images/,
             templates/, every .bat at the root, README.md, CHANGELOG.md,
             LICENSE, requirements.txt, requirements-dev.txt,
             pyproject.toml, pyrightconfig.json, .gitignore
  STAYS HERE .docs/, .agents/, .claude/, CLAUDE.md, GEMINI.md, .vscode/,
             dev-flags.toml, userdata/

Distribution for a novice: clone, run vdict_install.bat, launch once so the
model downloads, then create_usb_stick.bat for any machine without internet
or Python. LATER, NOT NOW: publish the stick folder as a zip on the repo's
Releases page so nobody needs a working install first. GitHub caps a
release file at 2 GB; the folder with one model is right around that.

## P1. README, MEDIA AND DISCOVERABILITY
SCREENSHOTS -- NONE
  The tray and Settings screenshots were deleted 2026-10-25; the README
  stands on its tables. If one comes back, it goes under "### Settings" as
  a clickable thumbnail with alt text naming the four boxes.

DEMO CLIP -- OUTSTANDING
  The placeholder demo.gif and its README line were deleted 2026-10-25.
  The clip goes back right after the "Why you might want it" bullets.

  What to capture: roughly 5 seconds -- hold the button, speak a sentence,
  text lands at the cursor. Something recognizable (VS Code, a browser
  search box).

  FORMAT: MP4, NOT GIF. GitHub strips <video> tags from rendered markdown,
  so an MP4 committed to the repo never plays inline. The only upload path
  that works: push the repo, drag the MP4 into a GitHub issue comment box
  (do not submit the issue), GitHub hands back a
  github.com/user-attachments/assets/... URL, paste that into README.md.
  Requires the repo to already be pushed.

  Keep it short, large media is slow on mobile.

"WHAT THIS RECORDS" SECTION -- OUTSTANDING, WRITE THIS ONE
  A named section in README.md, not a general instruction to make the README
  accurate. Three things, in this order: every file the app writes that
  contains the user's own words, where it puts them, and how to switch each
  one off. Name them literally --
  userdata/voice_recordings_PRIVATE, userdata/dictation_history_PRIVATE.db,
  userdata/logs/transcript_log.txt -- so someone can grep the source and
  confirm the list is complete.
  It is the only place the privacy work becomes visible. dev-flags.toml
  keeping a handed-out copy silent, userdata never riding along in a copy,
  the PRIVATE filenames -- all of it is invisible to anyone who does not read
  the code. The posture is that we know what we store, we are not hiding it,
  and we made it easy to find. Nothing states that today.
  Say it plainly and do not inflate it. The section is a fact list, not a
  privacy pledge.

SEO FINDING
  The README describes the app accurately but never uses the words people
  actually search for. Re-count before acting on this: offline 0, speech to
  text / speech-to-text 0, speech recognition 0, voice typing 0, open source 0,
  privacy/private 0. dictation 5, Whisper 6, transcri* 6. It already says
  "Nothing leaves your machine" and "runs on your own PC," which mean
  offline and privacy without ever saying either word -- naming the thing
  accurately, not inflating it, every missing term is literally true.

PUSH-DAY ACTIONS (blocked: the public repo does not exist yet)
  - Repo topics: single biggest lever, github.com/topics/<x> browsing plus
    weighted in GitHub's own search. Limit 20, currently zero. Proposed 19:
    speech-to-text, dictation, whisper, faster-whisper, push-to-talk,
    speech-recognition, voice-typing, offline, privacy, windows, python,
    stt, system-tray, accessibility, ai, llm, transcription, no-cloud,
    game-chat. Set via repo settings or gh repo edit --add-topic <t>. One
    slot left -- candidate: pystray (the tray is a working example of a
    Windows system-tray app in Python, worth a factual line in the README).
  - Repo description: the About blurb, heavily weighted in GitHub search
    and shown in search results. Currently unset.
  - A tagged release: indexed separately from the repo, gives people a
    download target instead of a clone.
  - PROJECT_URL (github.com/msromike/voice_dictation) is private today --
    Help > Documentation, F1, and the About box all open a dead link for
    anyone else. Resolves itself on push if the public repo name matches
    exactly -- verify after pushing.

README CHANGES (do-able now, deliberately deferred)
  - First ~155 characters: Google's meta description. Keep the "Hold a
    button, talk..." hook, follow it with one flat sentence naming the
    category -- offline speech-to-text / voice dictation for Windows,
    Whisper, no account.
  - Weave the six missing SEO terms into existing prose, not a keyword
    block -- e.g. "Nothing leaves your machine" becomes "Nothing leaves
    your machine -- it works fully offline." Same sentence, same tone.
  - Alt text on the three images is already descriptive and keyword-
    bearing -- just don't lose it in a future rewrite.
  - "Similar projects" section (Talon, WhisperWriter, Windows Voice
    Access) -- undecided, has tone risk. The one item here that adds a
    claim rather than renaming an existing one.

EXPLICITLY REJECTED
  Badges, keyword footers, emoji headings, awesome-list submissions before
  the repo has any history -- read as AI slop, cost more than the traffic
  is worth. Badges are SEO-worthless besides.
  Awesome-list submissions reopen once the repo has real history. The other
  three do not reopen on any condition anyone has named.

ACCURACY CATCHALL
  - Multilingual dictation: the engine is pinned to English since c6329bc.
    Do not claim multilingual.
  - Exclusive-mode conflict: Known Limitations should note that another
    app holding the mic in WASAPI exclusive mode blocks dictation until
    released or a different device is picked. True today; say it.
  - Windows-default-device recommendation: the README's advice to set your
    mic as Windows default becomes wrong if backlog.md's MIC HANDLING entry
    ever ships. Same gate.

## P2. AUTOMATED CHECKS
All three at zero:

    python -m ruff check .
    python -m pyright
    python tools\check_docstrings.py

## P3. VERSION AND CHANGELOG
__version__ bumped in vdict/__init__.py and vdict_daemon.py. Grep the tree
for other declarations before bumping; every one must match.
CHANGELOG.md [Unreleased] promoted to a dated version matching it.

## P4. README AND MEDIA
No stale menu labels or button text. Grep the README for any string the code
no longer uses.

images\ holds the icon and its source only. Any screenshot added since
matches the current UI.

## P5. BATCH FILES -- GREP, THEN ACTUALLY RUN THEM
A passing grep proves the filenames are spelled right. It does not prove
the scripts work -- a shortcut created with a syntax or quoting bug still
"succeeds" with no error and points at nothing useful. Both checks matter,
neither one alone is enough.

STATIC FIRST -- cheap, catches obvious naming staleness fast:

    grep -rn "\.bat" --include="*.md" --include="*.bat" --include="*.py" \
        --include="*.toml" --include="*.md" .

Cross-check every hit's filename against what's actually in the repo root.
CHANGELOG.md entries describing past releases are exempt -- historical
record, not live documentation.

THEN RUN EVERY BATCH FILE FOR REAL -- Mike runs, reports:
  vdict_install.bat and startup_folder_install.bat -- covered by P8's
    clean-clone install.
  vdict_run.bat -- covered by P7's smoke test.
  startup_folder_uninstall.bat -- NO coverage anywhere else. Run it, then
    confirm the VoiceDictation.lnk shortcut is actually gone from the
    Startup folder afterward -- not just that the script exited without an
    error.
  create_usb_stick.bat and the stick's install.bat -- todo.md has the
    test: a real stick, a second local account, Wi-Fi off.

Found the hard way: a batch of renames left stale text references scattered
across the tree, including a call to a batch file that no longer existed. The
grep above would have caught every one of them. None of those were the "runs
fine, does the wrong thing" kind, but that category exists and only running the
script for real catches it.

## P6. REPO HYGIENE
Nothing staged carrying an absolute local path or personal information.
The SHIPS / STAYS HERE list at the top of this file is the authority; grep
the cleaned copy for "msromike", "C:\\bin", "C:\\Users" before the first
push.

## P7. SMOKE TEST IN THE WORKING TREE
Launch vdict_run.bat. It runs the global Python; there is no venv.

## P8. CLEAN-CLONE INSTALL
Must be a CLONE, not the working tree. vdict_install.bat run in place proves
nothing about a fresh install.

Clone to an empty folder. Run vdict_install.bat, then startup_folder_install.bat.

Verify both shortcuts carry the icon. Launch from the Desktop shortcut.

## P9. DEV-ONLY CAPTURE FLAGS OFF
Dev flags default off in the shipped code, verify by confirming the flag
file is absent, not by memory:

  dev-flags.toml: capture_corpus -- PTT-mode utterance capture for the
    voice-ID corpus.

Not a Settings-exposed choice -- a shipped user never captures audio for
this purpose, on purpose. On for dev/corpus work, off before any push.
This file is gitignored and does not ship.
