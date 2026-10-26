@echo off
setlocal
:: Updates this copy from GitHub. The work is in update.ps1, run from a copy in
:: userdata\updates because the update replaces both files.
set "APP=%~dp0"
set "APP=%APP:~0,-1%"
if exist "%APP%\.git" (echo This folder is a git clone. Update it with git pull instead. & pause & exit /b 1)
if not exist "%APP%\userdata" (echo No userdata folder here, so this is not an installed copy yet. Run vdict_install.bat and launch Voice Dictation once first. & pause & exit /b 1)
if not exist "%APP%\userdata\updates" mkdir "%APP%\userdata\updates"
copy /y "%APP%\update.ps1" "%APP%\userdata\updates\update.ps1" >nul || (echo Could not copy the updater. & pause & exit /b 1)
:: One line, so cmd never reads this file again after the update replaces it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%APP%\userdata\updates\update.ps1" -App "%APP%" & exit /b
