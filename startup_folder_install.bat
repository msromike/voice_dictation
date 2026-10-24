@echo off
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_FOLDER%\VoiceDictation.lnk"
set "VDICT_TRAY=%~dp0voice-dictation\vdict_tray.py"

:: No venv. Use pythonw next to whatever `python` resolves to on PATH.
for /f "delims=" %%P in ('where python') do (set "PYTHONW_PATH=%%~dpPpythonw.exe" & goto :found)
echo [ERROR] python not found on PATH.
pause
exit /b 1
:found
if not exist "%PYTHONW_PATH%" (
    echo [ERROR] %PYTHONW_PATH% not found.
    pause
    exit /b 1
)

echo Installing Voice Dictation to Windows Startup...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); $Shortcut.TargetPath = '%PYTHONW_PATH%'; $Shortcut.Arguments = '\"%VDICT_TRAY%\"'; $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.IconLocation = '%~dp0images\vdict.ico'; $Shortcut.Description = 'Voice Dictation Tray'; $Shortcut.Save()"

echo Done! Voice dictation will launch automatically on next login.
