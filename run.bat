@echo off
title FILE XTRACTOR — Modern AI Desktop
cd /d "%~dp0"
set "PATH=C:\Program Files\nodejs;%PATH%"

echo ===================================================
echo   Starting FILE XTRACTOR Premium AI Desktop App
echo ===================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launch_app.py %*
) else (
    python launch_app.py %*
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)
