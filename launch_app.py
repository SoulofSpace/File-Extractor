"""
launch_app.py — Master Desktop Launcher for FILE XTRACTOR.
Starts the local Python AI/retrieval FastAPI bridge and launches the Electron desktop shell.
"""

from __future__ import annotations

import os
import sys
import time
import urllib.request
import subprocess
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)

API_PORT = 8765
API_URL = f"http://127.0.0.1:{API_PORT}"


def ensure_frontend_built() -> None:
    dist = FRONTEND / "dist"
    if not dist.exists() or not (dist / "index.html").exists():
        print("[Launcher] Building frontend production bundle...")
        cmd = 'set PATH=C:\\Program Files\\nodejs;%PATH% && cd frontend && npm.cmd run build'
        subprocess.run(cmd, shell=True, check=True, cwd=str(ROOT))


def check_server_running() -> bool:
    try:
        req = urllib.request.Request(f"{API_URL}/api/status", headers={"User-Agent": "IntelliFileLauncher/3.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_backend() -> subprocess.Popen:
    if check_server_running():
        print(f"[Launcher] Backend already running on {API_URL}.")
        return None

    print(f"[Launcher] Starting FILE XTRACTOR AI backend server on {API_URL}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "intellifile.api.server"],
        cwd=str(ROOT),
        env=env,
    )

    # Wait up to 15s for the server to be ready
    for _ in range(30):
        if check_server_running():
            print("[Launcher] AI Backend bridge is healthy and ready!")
            break
        time.sleep(0.5)

    return proc


def launch_electron() -> int:
    print("[Launcher] Launching FILE XTRACTOR Electron Desktop Shell...")
    cmd = 'set PATH=C:\\Program Files\\nodejs;%PATH% && cd frontend && npx.cmd electron .'
    res = subprocess.run(cmd, shell=True, cwd=str(ROOT))
    return res.returncode


def main():
    if any(arg in sys.argv for arg in ("--legacy", "--old-ui", "--qt")):
        print("[Launcher] Redirecting to legacy PySide6 UI...")
        src_path = ROOT / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        from intellifile.app import run as run_legacy
        run_legacy()
        return

    use_web = "--web" in sys.argv or "--browser" in sys.argv
    ensure_frontend_built()
    backend_proc = start_backend()

    try:
        if use_web:
            print(f"[Launcher] Opening FILE XTRACTOR in default browser at {API_URL}...")
            webbrowser.open(API_URL)
            print("[Launcher] Server running. Press Ctrl+C to stop.")
            if backend_proc:
                backend_proc.wait()
            else:
                while True:
                    time.sleep(1)
        else:
            code = launch_electron()
            if code != 0:
                print(f"[Launcher] Electron exited with code {code}. Falling back to browser view...")
                webbrowser.open(API_URL)
                if backend_proc:
                    backend_proc.wait()
    except KeyboardInterrupt:
        print("\n[Launcher] Shutting down...")
    finally:
        if backend_proc and backend_proc.poll() is None:
            print("[Launcher] Terminating AI backend process...")
            backend_proc.terminate()


if __name__ == "__main__":
    main()
