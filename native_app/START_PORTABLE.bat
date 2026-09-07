@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Kokoro SRT Portable

set "PYVER=3.12.8"
set "RUNTIME=%~dp0runtime"
set "PYDIR=%RUNTIME%\python"
set "PYEXE=%PYDIR%\python.exe"
set "PYWEXE=%PYDIR%\pythonw.exe"
set "PYSETUP=%RUNTIME%\python-setup.exe"
set "PYLOG=%RUNTIME%\python-install.log"
set "READY=%RUNTIME%\.ready"
set "MODELDIR=%~dp0models"
set "MODEL=%MODELDIR%\kokoro-v1.0.int8.onnx"
set "VOICES=%MODELDIR%\voices-v1.0.bin"

if not exist "%RUNTIME%" mkdir "%RUNTIME%"
if not exist "%MODELDIR%" mkdir "%MODELDIR%"

if not exist "%PYEXE%" (
  echo [1/4] Preparing private Python %PYVER% x64...
  echo No admin rights and no system Python are required.
  echo.
  echo Downloading Python installer...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest ('https://www.python.org/ftp/python/' + $env:PYVER + '/python-' + $env:PYVER + '-amd64.exe') -OutFile $env:PYSETUP"
  if errorlevel 1 goto :download_error

  if exist "%PYDIR%" rmdir /s /q "%PYDIR%"
  if exist "%READY%" del /q "%READY%" 2>nul

  echo Installing Python only inside this app folder...
  echo A small Python installer progress window may appear.
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$a=@('/passive','InstallAllUsers=0',('TargetDir=' + $env:PYDIR),'Include_exe=1','Include_lib=1','Include_pip=1','Include_tcltk=1','Include_launcher=0','Include_test=0','Include_doc=0','Shortcuts=0','AssociateFiles=0','PrependPath=0','/log',$env:PYLOG); $p=Start-Process -FilePath $env:PYSETUP -ArgumentList $a -Wait -PassThru; exit $p.ExitCode"
  if errorlevel 1 goto :python_error

  if not exist "%PYEXE%" goto :python_error
  del /q "%PYSETUP%" 2>nul
)

if not exist "%PYEXE%" goto :python_error

if not exist "%READY%" (
  echo [2/4] Installing local Kokoro libraries...
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
  echo [3/4] Downloading Kokoro voices...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile $env:VOICES"
  if errorlevel 1 goto :model_error
)

echo [4/4] Starting Kokoro SRT Local...
if exist "%PYWEXE%" (
  start "" "%PYWEXE%" "%~dp0portable_launcher.py"
) else (
  start "" "%PYEXE%" "%~dp0portable_launcher.py"
)
exit /b 0

:download_error
echo.
echo ERROR: Could not download Python installer.
echo Check your Internet connection or firewall.
goto :error

:python_error
echo.
echo ERROR: Python installation did not create:
echo %PYEXE%
echo.
echo Installer log:
echo %PYLOG%
echo.
echo Delete the runtime folder and run START_PORTABLE.bat again.
goto :error

:pip_error
echo.
echo ERROR: Python is installed, but Kokoro libraries failed to install.
echo Python: %PYEXE%
goto :error

:model_error
echo.
echo ERROR: Could not download the Kokoro model/voices.
echo You can retry later; existing Python setup will be reused.
goto :error

:error
echo.
echo ============================================================
echo Setup failed. The message above identifies the failed step.
echo No admin rights or system Python are required.
echo Everything is kept inside this app folder.
echo ============================================================
pause
exit /b 1
