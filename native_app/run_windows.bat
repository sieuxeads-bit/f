@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python venv...
  py -3.12 -m venv .venv
  if errorlevel 1 goto :error
)

echo [2/3] Installing/updating dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/3] Starting Kokoro SRT Local...
".venv\Scripts\python.exe" app.py
exit /b 0

:error
echo.
echo Failed. Install Python 3.12 x64, then run this file again.
pause
exit /b 1
