@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Kokoro SRT Studio - CLEAN R2

set "ROOT=%LOCALAPPDATA%\KokoroSRT"
set "MODELDIR=%ROOT%\models"
set "MODEL_FP32=%MODELDIR%\kokoro-v1.0.onnx"
set "MODEL_FP32_MARKER=%ROOT%\.kokoro_model_fp32_v11"

if not exist "%ROOT%" mkdir "%ROOT%"
if not exist "%MODELDIR%" mkdir "%MODELDIR%"

echo [CLEAN R2] FP32 + anti-re + legacy High Prosody guard

if not exist "%MODEL_FP32%" goto :download_fp32
if not exist "%MODEL_FP32_MARKER%" goto :download_fp32
goto :fp32_ready

:download_fp32
echo [Clean Quality] Downloading Kokoro FP32 full-precision model - about 326 MB...
echo This is a one-time download to avoid FP16 static/high-frequency artifacts.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $tmp=$env:MODEL_FP32 + '.new'; Invoke-WebRequest 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx' -OutFile $tmp; Move-Item -Force $tmp $env:MODEL_FP32"
if errorlevel 1 goto :model_error
>"%MODEL_FP32_MARKER%" echo ready

:fp32_ready
set "KOKORO_CLEAN_MODEL=%MODEL_FP32%"
set "KOKORO_CLEAN_BUILD=CLEAN_R2"
call "%~dp0START_QUALITY.bat"
exit /b %errorlevel%

:model_error
echo.
echo ERROR: Could not download the Kokoro FP32 clean model.
echo Running START_PORTABLE.bat again will retry the download.
echo Cache: %ROOT%
pause
exit /b 1
