@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Kokoro SRT Portable

set "PYVER=3.12.8"
set "RUNTIME=%CD%\runtime"
set "PYDIR=%RUNTIME%\python"
set "PYEXE=%PYDIR%\python.exe"
set "PYWEXE=%PYDIR%\pythonw.exe"
set "PYZIP=%RUNTIME%\python-embed.zip"
set "GETPIP=%RUNTIME%\get-pip.py"
set "READY=%RUNTIME%\.ready"
set "MODELDIR=%CD%\models"
set "MODEL=%MODELDIR%\kokoro-v1.0.int8.onnx"
set "VOICES=%MODELDIR%\voices-v1.0.bin"

if not exist "%RUNTIME%" mkdir "%RUNTIME%"
if not exist "%MODELDIR%" mkdir "%MODELDIR%"

if not exist "%PYEXE%" (
  echo [1/4] Downloading portable Python %PYVER% x64...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip' -OutFile '%PYZIP%'"
  if errorlevel 1 goto :error

  echo Extracting Python...
  if exist "%PYDIR%" rmdir /s /q "%PYDIR%"
  mkdir "%PYDIR%"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%PYZIP%' -DestinationPath '%PYDIR%' -Force"
  if errorlevel 1 goto :error
  del /q "%PYZIP%" 2>nul

  if exist "%PYDIR%\python312._pth" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$p='%PYDIR%\python312._pth'; $c=Get-Content -Raw $p; $c=$c.Replace('#import site','import site'); Set-Content -LiteralPath $p -Value $c -Encoding ASCII"
    if errorlevel 1 goto :error
  )
)

if not exist "%READY%" (
  echo [2/4] Installing local Python libraries...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%GETPIP%'"
  if errorlevel 1 goto :error

  "%PYEXE%" "%GETPIP%" --no-warn-script-location
  if errorlevel 1 goto :error

  set PIP_DISABLE_PIP_VERSION_CHECK=1
  "%PYEXE%" -m pip install --no-warn-script-location -r "%CD%\requirements.txt"
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
echo ============================================================
pause
exit /b 1
