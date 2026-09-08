@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Keep one Windows entry point. The portable launcher handles Python,
rem dependencies, GPU runtime, models, and CPU fallback automatically.
call "%~dp0START_PORTABLE.bat"
exit /b %errorlevel%
