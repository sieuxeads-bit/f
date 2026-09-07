@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Kokoro SRT Portable

set "PYVER=3.12.8"
set "RUNTIME=%CD%\runtime"
set "PYDIR=%RUNTIME%\python"
set "PYEXE=%PYDIR%\python.exe"
set "PYWEXE=%PYDIR%\pythonw.exe"
set "PYSETUP=%RUNTIME%\python-setup.exe"
set "READY=%RUNTIME%\.ready"
set "MODELDIR=%CD%\models"
set "MODEL=%MODELDIR%\kokoro-v1.0.int8.onnx"
set "VOICES=%MODELDIR%\voices-v1.0.bin"

if not exist "%RUNTIME%" mkdir "%RUNTIME%"
if not exist "%MODELDIR%" mkdir "%MODELDIR%"

if not exist "%PYEXE%" (
  echo [1/4] Preparing private Python %PYVER% x64...
  echo No admin rights and no system Python are required.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-amd64.exe' -OutFile '%PYSETUP%'"
  if errorlevel 1 goto :error

  if exist "%PYDIR%" rmdir /s /q "%PYDIR%"
  echo Installing Python only inside this app folder...
  start /wait "" "%PYSETUP%" /quiet InstallAllUsers=0 TargetDir="%PYDIR%" Include_pip=1 Include_tcltk=1 Include_launcher=0 Include_test=0 Include_doc=0 Shortcuts=0 AssociateFiles=0 PrependPath=0
  if errorlevel 1 goto :error
  del /q "%PYSETUP%" 2>nul
)

if not exist "%READY%" (
  echo [2/4] Installing local Kokoro libraries...
  set PIP_DISABLE_PIP_VERSION_CHECK=1
  "%PYEXE%" -m pip install --upgrade pip
  if errorlevel 1 goto :error
  "%PYEXE%" -m pip install -r "%CD%\requirements.txt"
  if errorlevel 1 goto :error
  >"%READY%" echo ready
)

if not exist "%MODEL%" (
  echo [3/4] Downloading Kokoro INT8 model - about 88 MB...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx' -OutFile '%MODEL%'"
  if errorlevel 1 goto :error
)

if not exist "%VOICES%" (
  echo [3/4] Downloading Kokoro voices...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile '%VOICES%'"
  if errorlevel 1 goto :error
)

echo [4/4] Starting Kokoro SRT Local...
if exist "%PYWEXE%" (
  start "" "%PYWEXE%" "%CD%\portable_launcher.py"
) else (
  start "" "%PYEXE%" "%CD%\portable_launcher.py"
)
exit /b 0

:error
echo.
echo ============================================================
echo Setup failed. Check your Internet connection and try again.
echo You do NOT need to install Python manually.
echo Everything is kept inside the runtime folder of this app.
echo ============================================================
pause
exit /b 1
