@echo off
setlocal
:: Downloads the latest version into userdata\updates and runs its tools\update.ps1,
:: so every update runs the newest update steps.
set "APP=%~dp0"
set "APP=%APP:~0,-1%"
set "UPD=%APP%\userdata\updates"
if exist "%APP%\.git" (echo This folder is a git clone. Update it with git pull instead. & pause & exit /b 1)
if not exist "%APP%\userdata" (echo No userdata folder here, so this is not an installed copy yet. Run vdict_install.bat and launch Voice Dictation once first. & pause & exit /b 1)
if not exist "%UPD%" mkdir "%UPD%"

echo == Downloading the latest version from GitHub
curl.exe -L --fail -o "%UPD%\main.zip" https://github.com/msromike/voice_dictation/archive/refs/heads/main.zip || goto :fail
if exist "%UPD%\extract" rmdir /s /q "%UPD%\extract"
mkdir "%UPD%\extract"
tar -xf "%UPD%\main.zip" -C "%UPD%\extract" || goto :fail
if not exist "%UPD%\extract\voice_dictation-main\tools\update.ps1" (echo The download does not look like Voice Dictation. & goto :fail)

:: One line, so cmd never reads this file again after the update replaces it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%UPD%\extract\voice_dictation-main\tools\update.ps1" & exit /b

:fail
echo.
echo [ERROR] The update stopped at the step above. Downloads are in %UPD%
pause
exit /b 1
