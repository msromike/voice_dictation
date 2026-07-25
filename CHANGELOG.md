# Changelog

## [1.0.0] - 2026-07-25
### Added
- Implemented dummy audio injection to initialize CUDA cores, removing the 1.5s cold-start latency.
- Replaced static text entry with an active event listener for PTT keybinding via `pynput`.
- Added a self-healing configuration architecture; `config.json` automatically regenerates if missing.
- Built automated installation batch scripts targeting isolated virtual environments (`venv`) to prevent global dependency conflicts.

## [0.9.0-alpha] - 2026-07-24
### Added
- Initial release prototype.
- Core STT transcription pipeline via `faster-whisper`.
- Windows System Tray integration and UI settings menu.
