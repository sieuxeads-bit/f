@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Kokoro SRT Local - One Click

set "ROOT=%LOCALAPPDATA%\KokoroSRT"
set "MAMBA=%ROOT%\micromamba.exe"
set "MAMBA_ROOT_PREFIX=%ROOT%\mamba_root"
set "ENV_DIR=%ROOT%\env"
set "PYEXE=%ENV_DIR%\python.exe"
set "PYWEXE=%ENV_DIR%\pythonw.exe"
set "READY=%ROOT%\.kokoro_ready_v3"
set "MODELDIR=%ROOT%\models"
set "MODEL=%MODELDIR%\kokoro-v1.0.int8.onnx"
set "VOICES=%MODELDIR%\voices-v1.0.bin"
set "MAMBA_URL=https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64"

if not exist "%ROOT%" mkdir "%ROOT%"
if not exist "%MODELDIR%" mkdir "%MODELDIR%"

if not exist "%MAMBA%" (
  echo [1/4] Downloading portable runtime manager...
  echo No Python installer. No admin rights. No registry changes.
  echo Cache: %ROOT%
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest $env:MAMBA_URL -OutFile $env:MAMBA"
  if errorlevel 1 goto :mamba_download_error
)

if not exist "%PYEXE%" (
  echo [1/4] Creating private Python 3.12 + Tkinter environment...
  echo This is a normal file extraction/package step, not a Windows installer.
  if exist "%ENV_DIR%" rmdir /s /q "%ENV_DIR%"
  "%MAMBA%" create -y -p "%ENV_DIR%" -c conda-forge python=3.12 tk pip
  if errorlevel 1 goto :mamba_create_error
)

if not exist "%PYEXE%" goto :mamba_create_error

"%PYEXE%" -c "import tkinter; print('Tkinter OK', tkinter.TkVersion)" >nul 2>&1
if errorlevel 1 goto :tk_error

if not exist "%READY%" (
  echo [2/4] Installing Kokoro ONNX libraries...
  set PIP_DISABLE_PIP_VERSION_CHECK=1
  "%PYEXE%" -m pip install --upgrade pip
  if errorlevel 1 goto :pip_error
  "%PYEXE%" -m pip install -r "%~dp0requirements.txt"
  if errorlevel 1 goto :pip_error
  >"%READY%" echo ready
)

if not exist "%MODEL%" (
  echo [3/4] Downloading Kokoro INT8 model - about 88 MB...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx' -OutFile $env:MODEL"
  if errorlevel 1 goto :model_error
)

if not exist "%VOICES%" (
  echo [3/4] Downloading Kokoro voices bundle...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile $env:VOICES"
  if errorlevel 1 goto :model_error
)

set "KOKORO_MODEL_DIR=%MODELDIR%"
echo [4/4] Starting Kokoro SRT Local...
echo Runtime and models will be reused automatically next time.
if exist "%PYWEXE%" (
  start "" "%PYWEXE%" "%~dp0portable_launcher.py"
) else (
  start "" "%PYEXE%" "%~dp0portable_launcher.py"
)
exit /b 0

:mamba_download_error
echo.
echo ERROR: Could not download micromamba portable runtime manager.
echo Check Internet/firewall access to GitHub.
goto :error

:mamba_create_error
echo.
echo ERROR: Could not create the private Python environment.
echo Cache folder: %ROOT%
echo.
echo To retry from zero, delete this folder only:
echo %ROOT%
goto :error

:tk_error
echo.
echo ERROR: Private Python was created but Tkinter is missing.
echo Delete %ROOT% and run this file again.
goto :error

:pip_error
echo.
echo ERROR: Python works, but Kokoro libraries failed to install.
echo Python: %PYEXE%
goto :error

:model_error
echo.
echo ERROR: Could not download the Kokoro model/voices.
echo Runtime is already ready; running this file again will retry only the missing files.
goto :error

:error
echo.
echo ============================================================
echo Setup failed at the step shown above.
echo Nothing is installed system-wide and admin rights are not needed.
echo Cache can always be deleted safely: %ROOT%
echo ============================================================
pause
exit /b 1
