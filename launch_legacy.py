"""
launch_legacy.py — Launches the legacy Qt/PySide6 FILE XTRACTOR interface (fallback).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
src_path = ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from intellifile.app import run

if __name__ == "__main__":
    print("[FILE XTRACTOR] Launching legacy Qt/PySide6 interface fallback...")
    run()
