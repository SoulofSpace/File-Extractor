"""
launch_app.py — Master Desktop Launcher for FILE XTRACTOR.
Starts the local Python AI/retrieval FastAPI bridge and launches the Electron desktop shell.
"""

from __future__ import annotations

import os
import sys
import time
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"

def ensure_frontend_built():
    dist = FRONTEND / "dist"
    if not dist.exists() or not (dist / "index.html").exists():
        print("[Launcher] Building frontend production bundle...")
        cmd = 'set PATH=C:\\Program Files\\nodejs;%PATH% && cd frontend && npm run build'
        subprocess.run(cmd, shell=True, check=True, cwd=str(ROOT))

def start_backend():
    print("[Launcher] Starting FILE XTRACTOR AI backend server on http://127.0.0.1:8765...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "intellifile.api.server"],
        cwd=str(ROOT),
        env=env,
    )
    return proc

def launch_electron():
    print("[Launcher] Launching FILE XTRACTOR Electron Desktop Shell...")
    cmd = 'set PATH=C:\\Program Files\\nodejs;%PATH% && cd frontend && npx electron .'
    subprocess.run(cmd, shell=True, cwd=str(ROOT))

def main():
    ensure_frontend_built()
    backend_proc = start_backend()
    time.sleep(2)  # Wait for server to bind

    try:
        launch_electron()
    finally:
        print("[Launcher] Shutting down backend...")
        backend_proc.terminate()

if __name__ == "__main__":
    main()
