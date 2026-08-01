@echo off
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_FOLDER%\VoiceDictation.lnk"
set "PYTHONW_PATH=%~dp0venv\Scripts\pythonw.exe"
set "VDICT_TRAY=%~dp0voice-dictation\vdict_tray.py"

if not exist "%PYTHONW_PATH%" (
    echo [ERROR] Virtual environment not found. Please run vdict_install.bat first.
    pause
    exit /b 1
)

echo Installing Voice Dictation to Windows Startup...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); $Shortcut.TargetPath = '%PYTHONW_PATH%'; $Shortcut.Arguments = '\"%VDICT_TRAY%\"'; $Shortcut.WorkingDirectory = '%~dp0'; $Shortcut.IconLocation = '%~dp0images\vdict.ico'; $Shortcut.Description = 'Voice Dictation Tray'; $Shortcut.Save()"

echo Done! Voice dictation will launch automatically on next login.
