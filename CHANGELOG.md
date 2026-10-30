# Changelog

## Unreleased

Changed: the Enter shortcut takes any key as well as a mouse button, so a mouse
whose software sends a key (F11, say) can press Enter without AutoHotkey. A held
key presses Enter once.

Added: `trace_ptt = true` in dev-flags.toml records every raw down and up of the
PTT and Enter keys or buttons to the history database, for diagnosing a trigger.

Fixed: a dictation pasted into Chrome sometimes arrived as nothing, or as the
old clipboard.

## 1.0.1 -- 2026-10-26

Fixed: the speech engine crashed after a dictation when the clipboard held
only a number. Cause: [pywin32 #2132](https://github.com/mhammond/pywin32/issues/2132).

## 1.0.0 -- 2026-10-26

Version 1.0.0 put on GitHub.
