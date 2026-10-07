@echo off
title i-file — Web Mode
cd /d "%~dp0"
set "PATH=C:\Program Files\nodejs;%PATH%"

echo ===================================================
echo   Starting i-file in Web Browser Mode
echo ===================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launch_app.py --web
) else (
    python launch_app.py --web
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)
