@echo off
setlocal
cd /d "%~dp0"

:: Install logs live with the app's own logs, survive updates, and are never in the zip.
set "LOGS=%~dp0userdata\logs\install"
if not exist "%LOGS%" mkdir "%LOGS%"
echo Install logs: %LOGS%
echo.

:: A fresh Windows has a "python" that only opens the Microsoft Store, so test by running it.
echo == Python: looking for 3.10 or newer
set "PY="
python -c "import sys; print('Found Python', sys.version); sys.exit(sys.version_info < (3, 10))" && set "PY=python"
if not defined PY call :install_python || goto :fail
"%PY%" -c "import sys; print(sys.executable)" > "%LOGS%\python-path.txt" || goto :fail
set /p PY=<"%LOGS%\python-path.txt"
for %%P in ("%PY%") do set "PYW=%%~dpPpythonw.exe"
echo Using %PY%

:: The speech engine needs MSVCP140.dll. Python ships the rest of the C++ runtime, not this.
echo.
echo == Visual C++ runtime: the speech engine needs MSVCP140.dll
if exist "%SystemRoot%\System32\msvcp140.dll" (echo Already installed.) else (call :install_vcredist || goto :fail)

:: No venv. Packages go into that Python.
echo.
echo == Packages: about 1.4 GB the first time, mostly NVIDIA CUDA libraries.
echo    This takes a while. Full log: %LOGS%\pip.log
"%PY%" -m pip install -r requirements.txt --log "%LOGS%\pip.log" || goto :fail

:: No trailing backslash: inside the shortcut's quoted strings it would escape the quote.
set "TARGET=%~dp0"
set "TARGET=%TARGET:~0,-1%"
set "TRAY=%TARGET%\voice-dictation\vdict_tray.py"

echo.
echo == Shortcuts: Desktop and Startup
call :shortcut Desktop "Voice Dictation.lnk" || goto :fail
call :shortcut Startup "VoiceDictation.lnk" || goto :fail

echo.
echo Setup complete. Launch Voice Dictation from the Desktop shortcut or vdict_run.bat.
echo It also starts on login; startup_folder_uninstall.bat turns that off.
pause
exit /b 0

:install_python
:: For this user only, so no admin prompt. PATH is set for new windows, not this one,
:: which is why PY is the full path.
echo No usable Python. Downloading Python 3.12.10 from python.org...
curl.exe -L --fail -o "%TEMP%\python-3.12.10-amd64.exe" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe || exit /b 1
echo Installing Python 3.12.10 for this user. Its progress window takes a minute or two.
echo Log: %LOGS%\python-install.log
"%TEMP%\python-3.12.10-amd64.exe" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0 /log "%LOGS%\python-install.log"
if errorlevel 1 (echo Python installer failed, exit code %errorlevel%. See the log above. & exit /b 1)
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (echo Python installer finished but %PY% does not exist. & exit /b 1)
echo Python installed: %PY%
exit /b 0

:install_vcredist
:: Microsoft's own package. It installs for the whole PC, so Windows asks for permission once.
echo Not found. Downloading Microsoft's Visual C++ Redistributable...
curl.exe -L --fail -o "%TEMP%\vc_redist.x64.exe" https://aka.ms/vs/17/release/vc_redist.x64.exe || exit /b 1
echo Installing it. Windows will ask for permission; click Yes.
echo Log: %LOGS%\vcredist.log
"%TEMP%\vc_redist.x64.exe" /install /passive /norestart /log "%LOGS%\vcredist.log"
set "RC=%errorlevel%"
:: 3010 means installed but wants a restart; 1638 means a newer one is already there.
if not "%RC%"=="0" if not "%RC%"=="3010" if not "%RC%"=="1638" (echo Visual C++ installer failed, exit code %RC%. See the log above. & exit /b 1)
if not exist "%SystemRoot%\System32\msvcp140.dll" (echo Visual C++ installer finished but MSVCP140.dll is still missing. & exit /b 1)
echo Visual C++ runtime installed.
exit /b 0

:shortcut
:: %1 is a special folder name (Desktop, Startup); %2 the shortcut's file name.
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('%~1') + '\%~2'); $s.TargetPath = '%PYW%'; $s.Arguments = '\"%TRAY%\"'; $s.WorkingDirectory = '%TARGET%'; $s.IconLocation = '%TARGET%\images\vdict.ico'; $s.Save()"
exit /b %errorlevel%

:fail
echo.
echo [ERROR] That step failed. Fix what it says above and run vdict_install.bat again.
echo Logs: %LOGS%
pause
exit /b 1
