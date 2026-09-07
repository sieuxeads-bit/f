@echo off
setlocal
cd /d "%~dp0"
if not exist models mkdir models

echo Downloading kokoro-v1.0.onnx...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx' -OutFile 'models\kokoro-v1.0.onnx'"
if errorlevel 1 goto :error

echo Downloading voices-v1.0.bin...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin' -OutFile 'models\voices-v1.0.bin'"
if errorlevel 1 goto :error

echo.
echo Done. Files saved in: %CD%\models
pause
exit /b 0

:error
echo.
echo Download failed. Check your internet connection and try again.
pause
exit /b 1
