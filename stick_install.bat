@echo off
setlocal
:: Runs from the USB stick as install.bat. Installs Voice Dictation, or updates it in
:: place, with no internet. create_usb_stick.bat puts it there.

set "STICK=%~dp0"
set "TARGET=%LOCALAPPDATA%\Programs\VoiceDictation"
set "PY=%TARGET%\python\python.exe"
set "PYW=%TARGET%\python\pythonw.exe"
set "TRAY=%TARGET%\voice-dictation\vdict_tray.py"

echo Installing Voice Dictation to %TARGET%
echo.

:: Killing the tray would leave its engine running, so the person exits it instead.
call :running || goto :not_running
echo Voice Dictation is running. Exit it from its tray icon, then press any key.
pause >nul
call :running || goto :not_running
echo It is still running. Nothing was changed.
pause
exit /b 1
:not_running

:: The app records its folder here on every launch, so a copy kept somewhere
:: else hands over its settings. Recordings never move.
set "OLD="
set "CARRIED="
for /f "tokens=2,*" %%A in ('reg query HKCU\Software\VoiceDictation /v InstallDir 2^>nul ^| findstr InstallDir') do set "OLD=%%B"
if defined OLD if /i not "%OLD%"=="%TARGET%" if exist "%OLD%\userdata" if not exist "%TARGET%\userdata" (
    echo [1/6] Settings from %OLD%
    call :robo "%OLD%\userdata" "%TARGET%\userdata" /E /XD voice_recordings_PRIVATE /XF dictation_history_PRIVATE.db || goto :fail
    set "CARRIED=1"
)

echo [2/6] Python
:: A mirror, so the packages go too: every install has exactly the stick's set.
call :robo "%STICK%python" "%TARGET%\python" /MIR || goto :fail

echo [3/6] App files
:: A mirror that leaves settings and Python alone, so code removed upstream goes.
call :robo "%STICK%app" "%TARGET%" /MIR /XD userdata python || goto :fail

echo [4/6] Packages -- a few minutes
:: -s everywhere: packages in this person's own Python folder must never load.
:: The private Python is never on PATH, by design, so pip's warning about it is noise.
:: 0, not 1: pip reads its "no-" options backwards. MEASURED; 1 still warns.
set "PIP_NO_WARN_SCRIPT_LOCATION=0"
:: ensurepip ignores that setting, so its output is kept back and shown only on failure.
"%PY%" -s -m ensurepip >"%TEMP%\vdict_ensurepip.txt" 2>&1 || (type "%TEMP%\vdict_ensurepip.txt" & goto :fail)
"%PY%" -s -m pip install --no-index --find-links "%STICK%wheels" -r "%TARGET%\requirements.txt" -q || goto :fail

echo [5/6] Speech models
"%PY%" -s -c "import os; print(os.environ.get('HF_HUB_CACHE') or os.path.join(os.environ.get('HF_HOME') or os.path.expanduser('~/.cache/huggingface'), 'hub'))" > "%TEMP%\vdict_hub.txt" || goto :fail
set /p HUB=<"%TEMP%\vdict_hub.txt"
for /d %%M in ("%STICK%models\models--*") do (
    if not exist "%HUB%\%%~nxM\refs\main" (
        echo       %%~nxM
        call :robo "%%M" "%HUB%\%%~nxM" /E || goto :fail
    )
)

echo [6/6] Desktop and Startup shortcuts
call :shortcut Desktop "Voice Dictation.lnk" || goto :fail
call :shortcut Startup "VoiceDictation.lnk" || goto :fail

echo.
echo Done. Starting Voice Dictation.
:: Says what happened, nothing more. That folder may be someone's working copy.
if defined CARRIED echo Your settings were copied from %OLD%. That folder was left as it was.
start "" /d "%TARGET%" "%PYW%" -s "%TRAY%"
pause
exit /b 0

:running
:: Succeeds when a Voice Dictation tray is running from any folder.
powershell -NoProfile -Command "if (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*vdict_tray.py*' }) { exit 0 } else { exit 1 }"
exit /b %errorlevel%

:shortcut
:: %1 is a special folder name (Desktop, Startup); %2 the shortcut's file name.
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('%~1') + '\%~2'); $s.TargetPath = '%PYW%'; $s.Arguments = '-s \"%TRAY%\"'; $s.WorkingDirectory = '%TARGET%'; $s.IconLocation = '%TARGET%\images\vdict.ico'; $s.Save()"
exit /b %errorlevel%

:robo
:: robocopy reports success as 0-7 and failure as 8 and above.
robocopy %* /NFL /NDL /NJH /NJS /NP >nul
if %errorlevel% geq 8 exit /b 1
exit /b 0

:fail
echo.
echo [ERROR] That step failed. Run install.bat again; it picks up where it is.
pause
exit /b 1
