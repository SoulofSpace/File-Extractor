@echo off
title FILE XTRACTOR — Modern AI Desktop
cd /d "%~dp0"
set "PATH=C:\Program Files\nodejs;%PATH%"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run.py %*
) else (
    python run.py %*
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)
