@echo off
title FILE XTRACTOR — Legacy UI (Fallback)
cd /d "%~dp0"

echo ===================================================
echo   Starting FILE XTRACTOR Legacy PySide6 UI
echo ===================================================

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launch_legacy.py %*
) else (
    python launch_legacy.py %*
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Legacy UI exited with code %ERRORLEVEL%.
    pause
)
