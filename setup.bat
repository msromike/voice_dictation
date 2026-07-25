@echo off
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat
echo Installing dependencies...
echo NOTE: This will download ~1GB of NVIDIA CUDA binaries so you don't have to install the toolkit manually. This may take a few minutes depending on your internet speed.
pip install -r requirements.txt
echo Setup complete! You can now run the app using run.bat
pause
