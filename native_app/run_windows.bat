@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_CMD="

rem Prefer Python 3.12 through the Windows Python Launcher when available.
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3.12"

rem Fall back to python.exe on PATH (works even when py.exe is not installed).
if not defined PY_CMD (
  python -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY_CMD=python"
)

rem Last fallback used by some installations.
if not defined PY_CMD (
  python3 -c "import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)" >nul 2>&1
  if not errorlevel 1 set "PY_CMD=python3"
)

if not defined PY_CMD goto :no_python

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python venv using: %PY_CMD%
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :error
) else (
  echo [1/3] Python venv already exists.
)

echo [2/3] Installing/updating dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/3] Starting Kokoro SRT Local...
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto :error
exit /b 0

:no_python
echo.
echo Python was not found.
echo Install Python 3.12 x64, then close and reopen this window.
echo.
echo Easy install from Command Prompt or PowerShell:
echo   winget install -e --id Python.Python.3.12
echo.
echo Or download Python from:
echo   https://www.python.org/downloads/release/python-31210/
echo.
pause
exit /b 1

:error
echo.
echo Failed. See the error above.
echo If Python was just installed, close this window and run the BAT again.
pause
exit /b 1
