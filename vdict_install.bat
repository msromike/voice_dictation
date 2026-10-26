@echo off
setlocal
cd /d "%~dp0"

:: A fresh Windows has a "python" that only opens the Microsoft Store, so test by running it.
set "PY="
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul && set "PY=python"
if not defined PY call :install_python || goto :fail
"%PY%" -c "import sys; print(sys.executable)" > "%TEMP%\vdict_py.txt" || goto :fail
set /p PY=<"%TEMP%\vdict_py.txt"
for %%P in ("%PY%") do set "PYW=%%~dpPpythonw.exe"
echo Using %PY%

:: No venv. Packages go into that Python.
echo.
echo Installing packages, about 1.4 GB the first time: the NVIDIA CUDA libraries
echo come with them, so nothing else needs installing. This takes a while.
"%PY%" -m pip install -r requirements.txt || goto :fail

:: No trailing backslash: inside the shortcut's quoted strings it would escape the quote.
set "TARGET=%~dp0"
set "TARGET=%TARGET:~0,-1%"
set "TRAY=%TARGET%\voice-dictation\vdict_tray.py"

echo.
echo Creating Desktop and Startup shortcuts...
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
echo Python 3.10 or newer was not found. Installing Python 3.12 for this user...
curl.exe -L --fail -o "%TEMP%\python-3.12.10-amd64.exe" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe || exit /b 1
"%TEMP%\python-3.12.10-amd64.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0 || exit /b 1
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" exit /b 1
exit /b 0

:shortcut
:: %1 is a special folder name (Desktop, Startup); %2 the shortcut's file name.
powershell -NoProfile -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('%~1') + '\%~2'); $s.TargetPath = '%PYW%'; $s.Arguments = '\"%TRAY%\"'; $s.WorkingDirectory = '%TARGET%'; $s.IconLocation = '%TARGET%\images\vdict.ico'; $s.Save()"
exit /b %errorlevel%

:fail
echo.
echo [ERROR] That step failed. Fix what it says above and run vdict_install.bat again.
pause
exit /b 1
