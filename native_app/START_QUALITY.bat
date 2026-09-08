@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Kokoro SRT Studio - High Quality Portable GPU

set "ROOT=%LOCALAPPDATA%\KokoroSRT"
set "MAMBA=%ROOT%\micromamba.exe"
set "MAMBA_ROOT_PREFIX=%ROOT%\mamba_root"
set "ENV_DIR=%ROOT%\env"
set "PYEXE=%ENV_DIR%\python.exe"
set "PYWEXE=%ENV_DIR%\pythonw.exe"
set "READY=%ROOT%\.kokoro_ready_v8"
set "MODELDIR=%ROOT%\models"
set "MODEL_CPU=%MODELDIR%\kokoro-v1.0.int8.onnx"
set "MODEL_GPU=%MODELDIR%\kokoro-v1.0.fp16.onnx"
set "VOICES=%MODELDIR%\voices-v1.0.bin"
set "CPU_MODEL_MARKER=%ROOT%\.kokoro_model_cpu_v11"
set "GPU_MODEL_MARKER=%ROOT%\.kokoro_model_gpu_v11"
set "VOICES_MARKER=%ROOT%\.kokoro_voices_v11"
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
  echo [2/5] Installing/updating Kokoro quality libraries...
  echo ONNX Runtime is managed separately so GPU and CPU packages never overwrite each other.
  set PIP_DISABLE_PIP_VERSION_CHECK=1
  "%PYEXE%" -m pip install --upgrade pip
  if errorlevel 1 goto :pip_error

  rem Dependencies that do NOT own ONNX Runtime DLLs.
  "%PYEXE%" -m pip install --upgrade "numpy>=2.0.2" "soundfile>=0.13.0" "espeakng-loader>=0.2.4" "phonemizer>=3.4.0" "num2words>=0.5.14"
  if errorlevel 1 goto :pip_error

  rem Do not let kokoro-onnx pull CPU onnxruntime over CUDA/DirectML.
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

rem model-files-v1.1 exports duration output used by create_timed and continuous prosody.
if not exist "%CPU_MODEL_MARKER%" goto :upgrade_cpu_model
if not exist "%MODEL_CPU%" goto :upgrade_cpu_model
goto :cpu_model_ready

:upgrade_cpu_model
echo [4/5] Downloading duration-capable Kokoro INT8 model v1.1 - about 114 MB...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $tmp=$env:MODEL_CPU + '.new'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.int8.onnx' -OutFile $tmp; Move-Item -Force $tmp $env:MODEL_CPU"
if errorlevel 1 goto :model_error
>"%CPU_MODEL_MARKER%" echo ready

:cpu_model_ready
if "!GPU_READY!"=="1" (
  if not exist "%GPU_MODEL_MARKER%" goto :upgrade_gpu_model
  if not exist "%MODEL_GPU%" goto :upgrade_gpu_model
)
goto :gpu_model_ready

:upgrade_gpu_model
echo [4/5] Downloading duration-capable Kokoro FP16 GPU model v1.1 - about 164 MB...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $tmp=$env:MODEL_GPU + '.new'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.fp16.onnx' -OutFile $tmp; Move-Item -Force $tmp $env:MODEL_GPU"
if errorlevel 1 (
  echo WARNING: High-quality FP16 GPU model download failed. CPU INT8 remains available.
  set "GPU_READY=0"
  goto :gpu_model_ready
)
>"%GPU_MODEL_MARKER%" echo ready

:gpu_model_ready
if not exist "%VOICES_MARKER%" goto :upgrade_voices
if not exist "%VOICES%" goto :upgrade_voices
goto :voices_ready

:upgrade_voices
echo [4/5] Downloading updated Kokoro v1.0 voices bundle...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $tmp=$env:VOICES + '.new'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin' -OutFile $tmp; Move-Item -Force $tmp $env:VOICES"
if errorlevel 1 goto :model_error
>"%VOICES_MARKER%" echo ready

:voices_ready
set "KOKORO_MODEL_DIR=%MODELDIR%"
echo [5/5] Starting Kokoro SRT Studio - Safe High Prosody...
if "!GPU_READY!"=="1" (
  echo GPU acceleration: READY
) else (
  echo GPU acceleration: unavailable - CPU mode active
)
echo Duration/prosody model cache: READY
echo Safe renderer: context max 2, quiet/zero-cross cuts, no group sliding joins

echo Runtime and models are cached in %ROOT%

if exist "%PYWEXE%" (
  start "" "%PYWEXE%" "%~dp0safe_quality_launcher.py"
) else (
  start "" "%PYEXE%" "%~dp0safe_quality_launcher.py"
)
exit /b 0


:setup_cuda
rem Reuse an already-working CUDA runtime before touching any DLL files.
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
echo ERROR: Kokoro quality libraries failed to update.
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
echo ERROR: Could not download the duration-capable Kokoro model/voices.
echo Running this file again will retry only the missing quality files.
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