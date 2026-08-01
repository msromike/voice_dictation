@echo off
cd /d "%~dp0"

:: Check for Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo =======================================================
    echo [FATAL ERROR] Python was not found on this system!
    echo =======================================================
    echo Please install Python 3.10+ from https://python.org
    echo IMPORTANT: Make sure to check the box that says 
    echo "Add python.exe to PATH" at the bottom of the installer!
    echo.
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat
echo Installing dependencies...
echo NOTE: This will download ~1.4GB of NVIDIA CUDA binaries so you don't have to install the toolkit manually. This may take a few minutes depending on your internet speed.
pip install -r requirements.txt
echo Creating Desktop and Startup shortcuts...
call startup_folder_install.bat
set "PYTHONW_PATH=%~dp0venv\Scripts\pythonw.exe"
set "VDICT_TRAY=%~dp0voice-dictation\vdict_tray.py"
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut(\"$HOME\Desktop\Voice Dictation.lnk\"); $Shortcut.TargetPath = '%PYTHONW_PATH%'; $Shortcut.Arguments = '\"%VDICT_TRAY%\"'; $Shortcut.WorkingDirectory = \"%~dp0\"; $Shortcut.IconLocation = \"%~dp0images\vdict.ico\"; $Shortcut.Save()"
echo Setup complete! You can now run the app from your Desktop or using vdict_run.bat
pause
