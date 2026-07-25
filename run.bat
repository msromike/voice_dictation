@echo off
echo Starting Voice Dictation...
call venv\Scripts\activate.bat
start pythonw voice-dictation\vdict_tray.py
