@echo off
setlocal
call "%~dp0START_QUALITY.bat"
exit /b %errorlevel%
