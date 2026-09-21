from __future__ import annotations

import os
from pathlib import Path


def application_data_dir() -> Path:
    """Return an application-owned location; never store copies of user files."""
    override = os.environ.get("INTELLIFILE_DATA_DIR")
    if override:
        app_dir = Path(override)
    else:
        root = os.environ.get("LOCALAPPDATA")
        base = Path(root) if root else Path.home() / ".local" / "share"
        app_dir = base / "IntelliFile"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def database_path() -> Path:
    return application_data_dir() / "intellifile.sqlite3"
