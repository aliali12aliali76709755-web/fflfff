@echo off
setlocal
cd /d "%~dp0"
title BotForge
where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python is not installed. Install Python 3.10+ from https://www.python.org/downloads/
  echo     and tick "Add python.exe to PATH" during setup, then run this file again.
  pause
  exit /b 1
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
  echo [X] Python 3.10 or newer is required.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating virtual environment...
  python -m venv .venv
)
echo [2/3] Installing requirements (first run takes a few minutes)...
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo [X] Failed to install requirements. Check your internet connection.
  pause
  exit /b 1
)
echo [3/3] Starting the bot server. Keep this window open. Press Ctrl+C to stop.
echo.
".venv\Scripts\python.exe" run.py
pause
