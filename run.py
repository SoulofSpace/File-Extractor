"""
run.py — Official Entry Point for FILE XTRACTOR.

Default: Launches the new Modern React + TypeScript Electron desktop application.
Fallback: Use --legacy or --old-ui to launch the legacy PySide6 interface.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
src_path = ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def main():
    if any(arg in sys.argv for arg in ("--legacy", "--old-ui", "--qt")):
        print("[FILE XTRACTOR] Starting legacy Qt/PySide6 UI fallback...")
        from intellifile.app import run as run_legacy
        run_legacy()
    else:
        from launch_app import main as launch_modern
        launch_modern()


if __name__ == "__main__":
    main()
