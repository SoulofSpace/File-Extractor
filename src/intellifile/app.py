"""
app.py — FILE XTRACTOR Main Application
Clean, human-designed workspace (Claude-inspired, non-AI):
  • Living interactive animated background covering full app
  • Sidebar OPEN by default on launch, smoothly collapsible via ◨
  • Large ALL CAPS title "FILE XTRACTOR" with letter scramble reveal
  • Natural OS cursor with smooth glowing luminous trail train effect
  • Direct file indexing and instant content retrieval
"""

from __future__ import annotations
import sys
import os
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout,
    QVBoxLayout, QStackedWidget, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent

# ── Auto sys.path ──────────────────────────────────────────────────────────────
_here = Path(__file__).resolve().parent
_src  = _here.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from intellifile.ui.styles             import DARK_STYLESHEET
from intellifile.ui.sidebar            import Sidebar
from intellifile.ui.search_view        import SearchView
from intellifile.ui.preview_pane       import PreviewPane
from intellifile.ui.folder_manager     import FolderManager
from PySide6.QtCore import QThreadPool
from intellifile.ui.status_bar         import StatusBarWidget
from intellifile.ui.diagnostics_view   import DiagnosticsView
from intellifile.ui.space_background   import InteractiveSpaceBackground
from intellifile.ui.cursor_trail       import CursorTrail, GlobalMouseTracker
from intellifile.database import Database
from intellifile.scanner  import ScanWorker
from intellifile.paths    import database_path
from intellifile.ai_agent import AIAgent
from intellifile.vector_store import SQLiteFlatVectorStore
from intellifile.embedding_provider import SentenceTransformerProvider
from intellifile.search_worker import SearchWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FILE XTRACTOR")
        self.setMinimumSize(1020, 700)
        self.resize(1260, 800)

        # Database, Vector Storage, & AI Agent
        self._db = Database(database_path())
        self._vector_store = SQLiteFlatVectorStore(database_path())
        self._embedding_provider = SentenceTransformerProvider()
        self._ai_agent = AIAgent(
            self._db,
            embedding_provider=self._embedding_provider,
            vector_store=self._vector_store,
        )
        self._thread_pool = QThreadPool.globalInstance()
        self._scan_worker: ScanWorker | None = None

        # Apply global stylesheet
        QApplication.instance().setStyleSheet(DARK_STYLESHEET)

        # ── Living Interactive Background as Central Widget ──
        # This guarantees full-screen coverage, automatic resizing, and active painting
        self._space_bg = InteractiveSpaceBackground(self)
        self.setCentralWidget(self._space_bg)

        # ── Root Layout inside the interactive canvas ─────────
        root_layout = QHBoxLayout(self._space_bg)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar (OPEN BY DEFAULT as requested) ─────────────
        self._sidebar = Sidebar(self._space_bg)
        self._sidebar.nav_changed.connect(self._on_nav)
        self._sidebar.close_requested.connect(self.toggle_sidebar)
        self._sidebar.add_folder_requested.connect(self._prompt_add_folder)
        self._sidebar.recent_file_clicked.connect(self._on_recent_file_clicked)
        self._sidebar.show()  # Starts OPEN!
        root_layout.addWidget(self._sidebar)

        # ── Main Area (Pages Stack + Preview + Status Bar) ─────
        main_area = QWidget()
        main_area.setStyleSheet("background: transparent;")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        pages_and_preview = QHBoxLayout()
        pages_and_preview.setContentsMargins(0, 0, 0, 0)
        pages_and_preview.setSpacing(0)

        self._stack = QStackedWidget()
        self._stack.setObjectName("mainStack")
        self._stack.setStyleSheet("background: transparent;")

        self._search_view    = SearchView()
        self._folder_manager = FolderManager()
        self._recent_view    = SearchView()
        self._diag_view      = DiagnosticsView()

        self._stack.addWidget(self._search_view)      # index 0
        self._stack.addWidget(self._folder_manager)   # index 1
        self._stack.addWidget(self._recent_view)      # index 2
        self._stack.addWidget(self._diag_view)        # index 3

        pages_and_preview.addWidget(self._stack, 1)

        # Right preview drawer
        self._preview = PreviewPane()
        pages_and_preview.addWidget(self._preview)

        main_layout.addLayout(pages_and_preview, 1)

        # Bottom status bar
        self._status_bar = StatusBarWidget()
        main_layout.addWidget(self._status_bar)

        root_layout.addWidget(main_area, 1)

        # ── Cursor Train Trail Overlay (Natural OS pointer + fluid trailing ribbon) ──
        self._cursor_trail = CursorTrail(self._space_bg)
        self._cursor_trail.resize(self.size())
        self._cursor_trail.raise_()

        # ── Global Mouse Tracker (Captures 100% mouse movement everywhere) ──
        self._mouse_tracker = GlobalMouseTracker(self._cursor_trail, self._space_bg)
        QApplication.instance().installEventFilter(self._mouse_tracker)

        # ── Signal Wiring ──────────────────────────────────────
        self._search_view.toggle_sidebar_requested.connect(self.toggle_sidebar)
        self._recent_view.toggle_sidebar_requested.connect(self.toggle_sidebar)
        self._search_view.search_requested.connect(self._on_search)
        self._search_view.file_selected.connect(self._preview.show_file)
        self._search_view.file_opened.connect(self._open_file)
        self._recent_view.file_selected.connect(self._preview.show_file)
        self._recent_view.file_opened.connect(self._open_file)
        self._preview.open_requested.connect(self._open_file)
        self._folder_manager.folder_added.connect(self._on_folder_added)
        self._folder_manager.folder_removed.connect(self._on_folder_removed)
        self._folder_manager.rescan_requested.connect(self._scan_folder)
        self._diag_view.rescan_all_requested.connect(self._rescan_all)

        # Update initial state
        self._load_folders()
        self._update_stats()
        self._refresh_sidebar_recents()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_cursor_trail') and self._cursor_trail:
            self._cursor_trail.setGeometry(self.rect())

    def toggle_sidebar(self):
        is_visible = self._sidebar.isVisible()
        if is_visible:
            self._sidebar.hide()
            self._search_view.set_menu_button_visible(True)
            self._recent_view.set_menu_button_visible(True)
        else:
            self._sidebar.show()
            self._search_view.set_menu_button_visible(False)
            self._recent_view.set_menu_button_visible(False)

    def _prompt_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Index")
        if folder:
            self._on_folder_added(folder)

    def _on_nav(self, key: str):
        mapping = {
            "search":      0,
            "folders":     1,
            "recent":      2,
            "diagnostics": 3,
        }
        idx = mapping.get(key, 0)
        self._stack.setCurrentIndex(idx)
        self._preview.hide()

        if key == "recent":
            self._load_recent()
        elif key == "diagnostics":
            self._refresh_diagnostics()

    def _on_search(self, query: str, category: str):
        self._status_bar.set_status(f"Searching: {query[:35]}...")
        cat_filter = None if category == "ALL" else category.lower()

        worker = SearchWorker(
            search_fn=self._ai_agent.search,
            query=query,
            category=cat_filter,
            limit=45,
            save_history_fn=self._db.add_search_history,
        )
        worker.signals.results_ready.connect(self._on_search_completed)
        worker.signals.error_occurred.connect(self._on_search_error)
        self._thread_pool.start(worker)

    def _on_search_completed(self, results: list, elapsed_ms: float, summary: str):
        self._search_view.display_results(results)
        self._status_bar.set_status(f"{len(results)} files found in {elapsed_ms:.1f}ms")
        self._refresh_sidebar_recents()

    def _on_search_error(self, err_msg: str):
        self._status_bar.set_status(f"Search Error: {err_msg}")

    def _load_recent(self):
        try:
            recent = self._db.get_recent_files(limit=25)
            self._recent_view.display_results(recent)
        except Exception:
            pass

    def _on_recent_file_clicked(self, path: str):
        try:
            p = Path(path)
            if p.exists():
                file_record = self._db.get_file_by_path(path)
                if file_record:
                    self._preview.show_file(file_record)
                else:
                    self._open_file(path)
        except Exception:
            self._open_file(path)

    def _refresh_sidebar_recents(self):
        try:
            recents = self._db.get_recent_files(limit=8)
            self._sidebar.update_recent_files(recents)
        except Exception:
            pass

    def _load_folders(self):
        try:
            folders = self._db.folders_with_counts()
            self._folder_manager.load_folders(folders)
        except Exception:
            pass

    def _on_folder_added(self, path: str):
        try:
            self._db.add_folder(path)
        except Exception:
            pass
        self._scan_folder(path)

    def _on_folder_removed(self, path: str):
        try:
            self._db.remove_folder(path)
        except Exception:
            pass
        self._update_stats()

    def _scan_folder(self, path: str):
        if self._scan_worker and self._scan_worker.isRunning():
            return
        self._current_scanning_folder = str(path)
        folder_name = Path(path).name or str(path)
        self._status_bar.set_indexing(folder_name)
        self._scan_worker = ScanWorker(path, self._db)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.completed.connect(self._on_scan_completed)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _rescan_all(self):
        folders = [f["path"] for f in self._db.folders_with_counts() if "path" in f]
        for f in folders:
            self._scan_folder(f)

    def _on_scan_progress(self, current: int, total: int, filename: str = ""):
        self._status_bar.set_progress(current, total)
        if filename:
            self._status_bar.set_status(f"Indexing ({current}/{total}): {filename[:35]}")
        if hasattr(self, '_current_scanning_folder') and self._current_scanning_folder:
            self._folder_manager.set_scanning_progress(
                self._current_scanning_folder, current, total, filename
            )

    def _on_scan_completed(self, total: int, failures: int):
        self._status_bar.set_idle(
            file_count=self._db.total_file_count(),
            folder_count=len(self._db.folders_with_counts())
        )
        msg = f"Indexed {total} files"
        if failures > 0:
            msg += f" ({failures} skipped/errors)"
        self._status_bar.set_status(msg)
        if hasattr(self, '_current_scanning_folder') and self._current_scanning_folder:
            self._folder_manager.set_folder_completed(self._current_scanning_folder, total)
        self._update_stats()
        self._load_folders()
        self._refresh_sidebar_recents()

    def _on_scan_failed(self, error: str):
        self._status_bar.set_status(f"Scan error: {error}")
        self._update_stats()

    def _update_stats(self):
        try:
            total = self._db.total_file_count()
            folders = self._db.folders_with_counts()
            self._sidebar.update_stats(total, len(folders))
            self._status_bar.set_idle(total, len(folders))
        except Exception:
            pass

    def _refresh_diagnostics(self):
        try:
            total   = self._db.total_file_count()
            folders = self._db.folders_with_counts()
            failed  = self._db.get_failed_files()
            indexed = total - len(failed)
            self._diag_view.update_stats(total, indexed, len(failed), len(folders))
            self._diag_view.load_failed_files(failed)
        except Exception:
            pass

    def _open_file(self, path: str):
        try:
            if not path:
                return
            p = Path(path).resolve()
            if not p.exists():
                self._status_bar.set_status(f"File not found: {p.name}")
                return
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)])
            else:
                subprocess.run(["xdg-open", str(p)])
            self._status_bar.set_status(f"Opened: {p.name}")
        except Exception as e:
            if sys.platform == "win32":
                try:
                    subprocess.Popen(['explorer', f'/select,{str(p)}'])
                    self._status_bar.set_status(f"Revealed in folder: {p.name}")
                    return
                except Exception:
                    pass
            self._status_bar.set_status(f"Cannot open: {e}")


def run():
    _src_dir = Path(__file__).resolve().parent.parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("FILE XTRACTOR")
    app.setOrganizationName("Dharun")

    from intellifile.ui.cyber_scramble import ensure_friday_font
    ensure_friday_font()

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()
