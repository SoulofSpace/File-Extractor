"""
watcher.py — Real-Time Filesystem Observer for FILE XTRACTOR V2.
Uses `watchdog` to monitor indexed folders for creations, modifications, and deletions.
Includes debounce buffering and intelligent exclusion of temp / VCS files (.git, .venv, etc.).
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from PySide6.QtCore import QObject, Signal

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


IGNORED_DIR_NAMES = {
    ".git", ".svn", ".hg", ".venv", "venv", "env", "__pycache__",
    "node_modules", ".idea", ".vscode", "AppData", "$RECYCLE.BIN",
    "System Volume Information",
}

IGNORED_EXTENSIONS = {
    ".tmp", ".temp", ".crdownload", ".part", ".swp", ".lock",
    ".log", ".bak", "~",
}


class _DebouncedEventHandler(FileSystemEventHandler):
    """Event handler that filters system noise and debounces rapid file writes."""

    def __init__(self, callback: Callable[[str, str], None], debounce_seconds: float = 0.5):
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._pending_timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _should_ignore(self, path_str: str) -> bool:
        p = Path(path_str)
        # Check parent folder names against blacklist
        for part in p.parts:
            if part in IGNORED_DIR_NAMES:
                return True
        # Check extensions
        if p.suffix.lower() in IGNORED_EXTENSIONS:
            return True
        # Check hidden or temporary files
        if p.name.startswith("~$") or p.name.startswith("."):
            return True
        return False

    def _dispatch_debounced(self, event_type: str, path_str: str) -> None:
        if self._should_ignore(path_str):
            return

        with self._lock:
            # Cancel any active pending timer for this exact path
            if path_str in self._pending_timers:
                self._pending_timers[path_str].cancel()

            # Schedule debounced callback
            timer = threading.Timer(
                self.debounce_seconds,
                self._fire_event,
                args=(event_type, path_str),
            )
            self._pending_timers[path_str] = timer
            timer.start()

    def _fire_event(self, event_type: str, path_str: str) -> None:
        with self._lock:
            self._pending_timers.pop(path_str, None)
        try:
            self.callback(event_type, path_str)
        except Exception:
            pass

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._dispatch_debounced("created", event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._dispatch_debounced("modified", event.src_path)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._dispatch_debounced("deleted", event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._dispatch_debounced("deleted", event.src_path)
            dest = getattr(event, "dest_path", None)
            if dest:
                self._dispatch_debounced("created", dest)


class FolderWatcher(QObject):
    """
    Qt-compatible wrapper managing watchdog observers for indexed folders.
    Emits `file_changed(event_type, path)` signals to the main application.
    """
    file_changed = Signal(str, str)  # (event_type: 'created'|'modified'|'deleted', file_path: str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._observer: Optional[Observer] = None
        self._watched_folders: Set[str] = set()
        self._is_running = False

    @property
    def is_available(self) -> bool:
        return WATCHDOG_AVAILABLE

    def start(self, folders: List[Path | str]) -> None:
        if not WATCHDOG_AVAILABLE or self._is_running:
            return

        try:
            self._observer = Observer()
            handler = _DebouncedEventHandler(callback=self._on_event)

            for f in folders:
                p = Path(f)
                if p.is_dir():
                    p_str = str(p.resolve())
                    self._observer.schedule(handler, p_str, recursive=True)
                    self._watched_folders.add(p_str)

            self._observer.daemon = True
            self._observer.start()
            self._is_running = True
        except Exception:
            self.stop()

    def add_folder(self, folder: Path | str) -> None:
        p = Path(folder)
        if not WATCHDOG_AVAILABLE or not self._is_running or not self._observer or not p.is_dir():
            return
        p_str = str(p.resolve())
        if p_str not in self._watched_folders:
            handler = _DebouncedEventHandler(callback=self._on_event)
            self._observer.schedule(handler, p_str, recursive=True)
            self._watched_folders.add(p_str)

    def stop(self) -> None:
        if self._observer and self._is_running:
            try:
                self._observer.stop()
                self._observer.join(timeout=2.0)
            except Exception:
                pass
            finally:
                self._observer = None
                self._is_running = False
                self._watched_folders.clear()

    def _on_event(self, event_type: str, path_str: str) -> None:
        self.file_changed.emit(event_type, path_str)
