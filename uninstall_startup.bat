@echo off
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_FOLDER%\VoiceDictation.lnk"

echo Removing Voice Dictation from Windows Startup...
if exist "%SHORTCUT_PATH%" (
    del "%SHORTCUT_PATH%"
    echo Successfully removed from startup.
) else (
    echo Shortcut not found in startup folder.
)
pause
