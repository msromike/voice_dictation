@echo off
cd /d "%~dp0"
echo Starting Voice Dictation...
:: No venv. Runs on the global Python (pythonw next to whatever `python` resolves to).
for /f "delims=" %%P in ('where python') do (set "PYTHONW=%%~dpPpythonw.exe" & goto :found)
echo [ERROR] python not found on PATH.
exit /b 1
:found
start "" "%PYTHONW%" voice-dictation\vdict_tray.py
