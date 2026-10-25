@echo off
setlocal
cd /d "%~dp0"
:: Writes <drive>:\VoiceDictation -- Python, the exact package versions this machine runs,
:: the speech models and the app. install.bat on the stick then needs no internet.
:: An allowlist: nothing reaches the stick unless it is named below.

where python >nul 2>nul || (echo [ERROR] python is not on PATH. & pause & exit /b 1)

set /p "DRIVE=Drive letter of the USB stick, for example E: "
set "DRIVE=%DRIVE::=%"
if "%DRIVE%"=="" (echo [ERROR] No drive letter given. & pause & exit /b 1)
if /i "%DRIVE%:"=="%SystemDrive%" (echo [ERROR] %DRIVE%: is this computer's own drive. & pause & exit /b 1)
if not exist "%DRIVE%:\" (echo [ERROR] There is no drive %DRIVE%:. & pause & exit /b 1)
set "STICK=%DRIVE%:\VoiceDictation"
set "SCRATCH=%TEMP%\vdict_stick"
if not exist "%SCRATCH%" mkdir "%SCRATCH%"

echo.
echo [1/5] Installer
if not exist "%STICK%" mkdir "%STICK%"
copy /y "stick_install.bat" "%STICK%\install.bat" >nul || goto :fail

echo [2/5] App files
:: Rebuilt from nothing every time, so a file dropped from the repo leaves the stick too.
if exist "%STICK%\app" rmdir /s /q "%STICK%\app"
call :robo "voice-dictation" "%STICK%\app\voice-dictation" /E /XD __pycache__ || goto :fail
call :robo "templates" "%STICK%\app\templates" /E || goto :fail
call :robo "images" "%STICK%\app\images" vdict.ico || goto :fail
call :robo "." "%STICK%\app" requirements.txt README.md LICENSE CHANGELOG.md || goto :fail

echo [3/5] Python
:: The base install only: packages come from the wheels, never from this machine's folders.
python -c "import sys; print(sys.base_prefix)" > "%SCRATCH%\pybase.txt" || goto :fail
set /p PYBASE=<"%SCRATCH%\pybase.txt"
call :robo "%PYBASE%" "%STICK%\python" /MIR /XD "%PYBASE%\Lib\site-packages" "%PYBASE%\Scripts" "%PYBASE%\Doc" "%PYBASE%\include" "%PYBASE%\libs" __pycache__ || goto :fail

echo [4/5] Packages -- about 2 GB the first time
:: Pinned to what this machine has installed. pip wheel builds the few packages
:: published only as source, here, so the stick holds nothing that needs building.
python -m pip freeze --all | findstr "==" > "%SCRATCH%\constraints.txt"
if exist "%STICK%\wheels" rmdir /s /q "%STICK%\wheels"
python -m pip wheel -r requirements.txt -c "%SCRATCH%\constraints.txt" -w "%STICK%\wheels" --progress-bar off -q || goto :fail

echo [5/5] Speech models -- several GB the first time
:: The same cache lookup as the app's own. robocopy follows the cache's links,
:: so real files land on the stick, which cannot hold links.
python -c "import os; print(os.environ.get('HF_HUB_CACHE') or os.path.join(os.environ.get('HF_HOME') or os.path.expanduser('~/.cache/huggingface'), 'hub'))" > "%SCRATCH%\hub.txt" || goto :fail
set /p HUB=<"%SCRATCH%\hub.txt"
for /d %%M in ("%HUB%\models--*whisper-*") do (
    echo       %%~nxM
    call :robo "%%M\refs" "%STICK%\models\%%~nxM\refs" /MIR /FFT || goto :fail
    call :robo "%%M\snapshots" "%STICK%\models\%%~nxM\snapshots" /MIR /FFT || goto :fail
)

echo.
powershell -NoProfile -Command "'Stick size: {0:N1} GB' -f ((Get-ChildItem -Recurse -File '%STICK%' | Measure-Object Length -Sum).Sum / 1GB)"
echo Done. On the other computer, open %DRIVE%:\VoiceDictation and run install.bat.
pause
exit /b 0

:robo
:: robocopy reports success as 0-7 and failure as 8 and above.
robocopy %* /NFL /NDL /NJH /NJS /NP >nul
if %errorlevel% geq 8 exit /b 1
exit /b 0

:fail
echo.
echo [ERROR] That step failed. The stick is incomplete -- run this again.
pause
exit /b 1
