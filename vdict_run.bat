@echo off
cd /d "%~dp0"
echo Starting Voice Dictation...
:: Direct call, never activate.bat -- that hardcodes an absolute VIRTUAL_ENV,
:: so a relocated copy would silently run the original tree's packages.
start "" venv\Scripts\pythonw.exe voice-dictation\vdict_tray.py
