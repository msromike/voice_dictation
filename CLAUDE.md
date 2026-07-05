# Voice Dictation
Stack: Python 3 / faster-whisper / sounddevice / pynput / pyautogui / pyperclip. Windows desktop PTT daemon (no server, no DB, no deploy target).

## Commit Protocol (project addition)
Extends the global Commit Protocol (~/.claude/CLAUDE.md) with one repo-specific
gate. Insert this between global step 1 (INGEST STATE) and step 2 (COMMIT
HEADER) -- fail fast before drafting a commit message for code that can't ship:
- Run the relevant test_*.py script (test_audio.py / test_ptt.py / test_stt.py)
  manually and confirm expected console output. Any failure -> HARD STOP:
  "Circuit Breaker Tripped: manual test script failed. Do not commit broken
  code. Fix the failing script or the underlying defect, then re-trigger
  'commit per protocol'." Do not draft a commit message or run git commit
  until it passes.

## SPOP
Propose chunks (end with question) -> approved -> implement 1 -> STOP -> "works" -> implement 2 -> STOP
Never propose+implement same turn. Never implement until Design+Interface+Test Plan clear.

## Code
- crash-fast: no null checks between internal modules
- validate at boundaries only (config.json, audio device, model input)
- fix lint immediately; install deps immediately; no workarounds
- ASCII only; docs TXT (MD needs permission)

## Test
Before complete: run the matching test_*.py script (test_audio.py / test_ptt.py / test_stt.py) manually and confirm expected console output.

## Terms
PTT=push-to-talk (middle mouse button toggle) | STT=speech-to-text (faster-whisper) | Daemon=vdict.py background process listening for PTT clicks
