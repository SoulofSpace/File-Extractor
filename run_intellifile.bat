@echo off
title FILE XTRACTOR
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" run.py
) else (
    python run.py
)
