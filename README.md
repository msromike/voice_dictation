# Voice Dictation

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Voice Dictation is an offline, zero-latency speech-to-text application powered by `faster-whisper`. It runs entirely on your local hardware, ensuring complete privacy, and features a World of Warcraft-style click-to-bind macro interface for global PTT (Push-To-Talk) input capture.

## Features

- **Zero-Lag GPU Primer**: A proprietary audio injection sequence pre-warms the CUDA cores, eliminating the typical 1.5s cold-start latency found in other local STT applications.
- **Hardware Agnostic**: Automatic detection and fallback between CPU and GPU compute devices.
- **Self-Healing Architecture**: Automatic regeneration of corrupted or missing configurations.
- **Native System Tray UI**: Manage settings, audio feedback, and hardware profiles seamlessly from your Windows taskbar.
- **Click-to-Bind Macros**: Bind any keyboard or mouse button to trigger dictation globally using raw event hooks via `pynput`.

## Installation

This application uses an isolated virtual environment (`venv`) to prevent global dependency conflicts with the 3GB CUDA toolkit and PyTorch binaries.

1. Clone or download this repository to your machine.
2. Run `setup.bat`. This will automatically:
   - Create a localized Python virtual environment.
   - Install all required PyTorch, CUDA, and Whisper dependencies.
   - Generate a Desktop shortcut.
   - Register the application in your Windows Startup folder.
3. Once installation completes, double-click the `Voice Dictation` desktop shortcut to launch the background daemon.

## Requirements
- Windows 10/11
- Python 3.10+ (Ensure "Add python.exe to PATH" is checked during installation)
- An active internet connection for the first run (to download the AI model)

## Architecture

- `vdict_tray.py`: The master process that renders the Windows System Tray UI, handles configuration editing, and manages the lifecycle of the daemon.
- `vdict.py`: The headless background daemon that captures raw `pynput` events, streams microphone audio, and processes `faster-whisper` transcriptions.

## License
MIT License
