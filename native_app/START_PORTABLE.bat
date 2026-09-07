@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Kokoro SRT Studio - Portable GPU

set "ROOT=%LOCALAPPDATA%\KokoroSRT"
set "MAMBA=%ROOT%\micromamba.exe"
set "MAMBA_ROOT_PREFIX=%ROOT%\mamba_root"
set "ENV_DIR=%ROOT%\env"
set "PYEXE=%ENV_DIR%\python.exe"
set "PYWEXE=%ENV_DIR%\pythonw.exe"
set "READY=%ROOT%\.kokoro_ready_v7"
set "MODELDIR=%ROOT%\models"
set "MODEL_CPU=%MODELDIR%\kokoro-v1.0.int8.onnx"
set "MODEL_GPU=%MODELDIR%\kokoro-v1.0.fp16.onnx"
set "VOICES=%MODELDIR%\voices-v1.0.bin"
set "MAMBA_URL=https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-64"
set "GPU_READY=0"
set "GPU_VENDOR=cpu"

if not exist "%ROOT%" mkdir "%ROOT%"
if not exist "%MODELDIR%" mkdir "%MODELDIR%"

if not exist "%MAMBA%" (
  echo [1/5] Downloading portable runtime manager...
  echo No Python installer. No admin rights. No registry changes.
  echo Cache: %ROOT%
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest $env:MAMBA_URL -OutFile $env:MAMBA"
  if errorlevel 1 goto :mamba_download_error
)

if not exist "%PYEXE%" (
  echo [1/5] Creating private Python 3.12 + Tkinter environment...
  if exist "%ENV_DIR%" rmdir /s /q "%ENV_DIR%"
  "%MAMBA%" create -y -p "%ENV_DIR%" -c conda-forge python=3.12 tk pip
  if errorlevel 1 goto :mamba_create_error
)

if not exist "%PYEXE%" goto :mamba_create_error

"%PYEXE%" -c "import tkinter; print('Tkinter OK', tkinter.TkVersion)" >nul 2>&1
if errorlevel 1 goto :tk_error

if not exist "%READY%" (
  echo [2/5] Installing/updating Kokoro libraries...
  echo ONNX Runtime is managed separately so GPU and CPU packages never overwrite each other.
  set PIP_DISABLE_PIP_VERSION_CHECK=1
  "%PYEXE%" -m pip install --upgrade pip
  if errorlevel 1 goto :pip_error

  rem Install Kokoro dependencies that do NOT own ONNX Runtime DLLs.
  "%PYEXE%" -m pip install --upgrade "numpy>=2.0.2" "soundfile>=0.13.0" "espeakng-loader>=0.2.4" "phonemizer>=3.4.0"
  if errorlevel 1 goto :pip_error

  rem Critical: --no-deps prevents kokoro-onnx from pulling the CPU
  rem onnxruntime package over an existing CUDA/DirectML installation.
  "%PYEXE%" -m pip install --upgrade --no-deps "kokoro-onnx==0.6.1"
  if errorlevel 1 goto :pip_error
  >"%READY%" echo ready
)

echo [3/5] Detecting GPU...
where nvidia-smi >nul 2>&1
if not errorlevel 1 set "GPU_VENDOR=nvidia"

if "!GPU_VENDOR!"=="cpu" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$names=(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name); if ($names -match 'Radeon|AMD.*Graphics|Intel.*Arc') { exit 0 } else { exit 1 }" >nul 2>&1
  if not errorlevel 1 set "GPU_VENDOR=directml"
)

if "!GPU_VENDOR!"=="nvidia" (
  echo NVIDIA GPU detected. Preparing CUDA ONNX Runtime...
  call :setup_cuda
) else if "!GPU_VENDOR!"=="directml" (
  echo AMD / Intel Arc GPU detected. Preparing DirectML...
  call :setup_directml
) else (
  echo No supported discrete GPU detected. Preparing CPU ONNX Runtime...
  call :setup_cpu
)

if not exist "%MODEL_CPU%" (
  echo [4/5] Downloading Kokoro INT8 CPU model...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx' -OutFile $env:MODEL_CPU"
  if errorlevel 1 goto :model_error
)

if "!GPU_READY!"=="1" if not exist "%MODEL_GPU%" (
  echo [4/5] Downloading Kokoro FP16 GPU model...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.fp16.onnx' -OutFile $env:MODEL_GPU"
  if errorlevel 1 (
    echo WARNING: FP16 GPU model download failed. CPU INT8 remains available.
    set "GPU_READY=0"
  )
)

if not exist "%VOICES%" (
  echo [4/5] Downloading Kokoro voices bundle...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile $env:VOICES"
  if errorlevel 1 goto :model_error
)

set "KOKORO_MODEL_DIR=%MODELDIR%"
echo [5/5] Starting Kokoro SRT Studio...
if "!GPU_READY!"=="1" (
  echo GPU acceleration: READY
) else (
  echo GPU acceleration: unavailable - CPU mode active
)
echo Runtime and models are cached in %ROOT%

if exist "%PYWEXE%" (
  start "" "%PYWEXE%" "%~dp0studio_launcher.py"
) else (
  start "" "%PYEXE%" "%~dp0studio_launcher.py"
)
exit /b 0


:setup_cuda
rem First reuse an already-working CUDA runtime. This avoids touching DLL files
rem that may be loaded by a previously opened Kokoro window.
"%PYEXE%" -c "import onnxruntime as o; getattr(o,'preload_dlls',lambda **k:None)(directory=''); assert 'CUDAExecutionProvider' in o.get_available_providers(); print(o.get_available_providers())" >nul 2>&1
if not errorlevel 1 (
  >"%ROOT%\.ort_cuda_1_26" echo ready
  set "GPU_READY=1"
  exit /b 0
)

echo CUDA provider is not active. Repairing the private ONNX Runtime...
echo Close any Kokoro SRT Studio window if Windows reports Access Denied here.
"%PYEXE%" -m pip uninstall -y onnxruntime onnxruntime-directml onnxruntime-gpu >nul 2>&1
"%PYEXE%" -m pip install --upgrade "onnxruntime-gpu[cuda,cudnn]==1.26.0"
if errorlevel 1 goto :cuda_fallback

"%PYEXE%" -c "import onnxruntime as o; o.preload_dlls(directory=''); assert 'CUDAExecutionProvider' in o.get_available_providers(); print(o.get_available_providers())"
if errorlevel 1 goto :cuda_fallback

>"%ROOT%\.ort_cuda_1_26" echo ready
set "GPU_READY=1"
exit /b 0

:cuda_fallback
echo WARNING: CUDA runtime could not be activated. Falling back to CPU ONNX Runtime...
call :setup_cpu_force
set "GPU_READY=0"
exit /b 0


:setup_directml
"%PYEXE%" -c "import onnxruntime as o; assert 'DmlExecutionProvider' in o.get_available_providers(); print(o.get_available_providers())" >nul 2>&1
if not errorlevel 1 (
  >"%ROOT%\.ort_dml_1_24_4" echo ready
  set "GPU_READY=1"
  exit /b 0
)

echo DirectML provider is not active. Repairing the private ONNX Runtime...
echo Close any Kokoro SRT Studio window if Windows reports Access Denied here.
"%PYEXE%" -m pip uninstall -y onnxruntime onnxruntime-gpu onnxruntime-directml >nul 2>&1
"%PYEXE%" -m pip install --upgrade "onnxruntime-directml==1.24.4"
if errorlevel 1 goto :dml_fallback

"%PYEXE%" -c "import onnxruntime as o; assert 'DmlExecutionProvider' in o.get_available_providers(); print(o.get_available_providers())"
if errorlevel 1 goto :dml_fallback

>"%ROOT%\.ort_dml_1_24_4" echo ready
set "GPU_READY=1"
exit /b 0

:dml_fallback
echo WARNING: DirectML could not be activated. Falling back to CPU ONNX Runtime...
call :setup_cpu_force
set "GPU_READY=0"
exit /b 0


:setup_cpu
"%PYEXE%" -c "import onnxruntime as o; assert 'CPUExecutionProvider' in o.get_available_providers(); print(o.get_available_providers())" >nul 2>&1
if not errorlevel 1 (
  set "GPU_READY=0"
  exit /b 0
)
call :setup_cpu_force
exit /b 0

:setup_cpu_force
"%PYEXE%" -m pip uninstall -y onnxruntime-gpu onnxruntime-directml onnxruntime >nul 2>&1
"%PYEXE%" -m pip install --upgrade "onnxruntime>=1.20.1"
if errorlevel 1 goto :ort_error
"%PYEXE%" -c "import onnxruntime as o; assert 'CPUExecutionProvider' in o.get_available_providers()" >nul 2>&1
if errorlevel 1 goto :ort_error
set "GPU_READY=0"
exit /b 0


:mamba_download_error
echo.
echo ERROR: Could not download micromamba portable runtime manager.
goto :error

:mamba_create_error
echo.
echo ERROR: Could not create the private Python environment.
echo Cache folder: %ROOT%
goto :error

:tk_error
echo.
echo ERROR: Private Python was created but Tkinter is missing.
echo Delete %ROOT% and run this file again.
goto :error

:pip_error
echo.
echo ERROR: Kokoro libraries failed to update.
echo If Kokoro SRT Studio is currently open, close it and run this BAT again.
echo Python: %PYEXE%
goto :error

:ort_error
echo.
echo ERROR: ONNX Runtime could not be repaired.
echo Close every Kokoro SRT Studio window, then run this BAT again.
goto :error

:model_error
echo.
echo ERROR: Could not download the Kokoro model/voices.
echo Running this file again will retry only missing files.
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
