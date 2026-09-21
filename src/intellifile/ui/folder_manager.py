"""
folder_manager.py — High-Tech Folder Management View
Includes:
  • Drop zone with dashed border & hover states
  • Glass folder cards with real-time QProgressBar
  • Live indexing status indicators (Scanning vs Up-To-Date)
  • Dynamic progress tracking per folder with filename display
"""

from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QScrollArea, QSizePolicy, QProgressBar
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent


class DropZone(QFrame):
    folder_dropped = Signal(str)
    folder_browsed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(130)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 20, 24, 20)

        icon_lbl = QLabel("⊕")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 28px; color: rgba(255,255,255,0.2);")
        layout.addWidget(icon_lbl)

        title = QLabel("Drop a folder here")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("OR")
        sub.setObjectName("dropSubtitle")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        browse_btn = QPushButton("BROWSE FOLDERS  →")
        browse_btn.setObjectName("primaryButton")
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._browse)
        layout.addWidget(browse_btn, 0, Qt.AlignCenter)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_browsed.emit(folder)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(
                "QFrame#dropZone { border: 2px dashed #ffffff; "
                "background-color: rgba(255, 255, 255, 0.08); border-radius: 20px; }"
            )

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet("")
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).is_dir():
                self.folder_dropped.emit(path)


class FolderCard(QFrame):
    rescan_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, path: str, file_count: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("folderCard")
        self._path = path
        self._file_count = file_count

        self.setStyleSheet("""
            QFrame#folderCard {
                background-color: #1e1e20;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 16px;
            }
            QFrame#folderCard:hover {
                border: 1px solid rgba(255, 255, 255, 0.28);
                background-color: #232326;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # ── Top row: icon + folder name + status dot ──────────
        top = QHBoxLayout()
        top.setSpacing(10)

        icon = QLabel("▤")
        icon.setStyleSheet("font-size: 18px; color: #ffffff;")
        top.addWidget(icon)

        folder_name = QLabel(Path(path).name or path)
        folder_name.setObjectName("folderName")
        folder_name.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        folder_name.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top.addWidget(folder_name, 1)

        self._state_badge = QLabel("✓ UP TO DATE" if file_count > 0 else "READY")
        self._state_badge.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.08);
            color: #d4d4d8;
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.5px;
        """)
        top.addWidget(self._state_badge)
        layout.addLayout(top)

        # ── Path sub-label ────────────────────────────────────
        path_lbl = QLabel(path)
        path_lbl.setWordWrap(False)
        path_lbl.setStyleSheet("color: #71717a; font-size: 11px;")
        layout.addWidget(path_lbl)

        # ── Sleek Progress Bar (Animated / Active during scan) ──
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setFixedHeight(5)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #ffffff;
                border-radius: 2px;
            }
        """)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # ── Stats + action buttons ────────────────────────────
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self._stats_lbl = QLabel(f"✓ {file_count} FILES INDEXED" if file_count > 0 else "0 FILES INDEXED")
        self._stats_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        bottom.addWidget(self._stats_lbl, 1)

        self._rescan_btn = QPushButton("RESCAN")
        self._rescan_btn.setCursor(Qt.PointingHandCursor)
        self._rescan_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #e4e4e7;
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.2);
                color: #71717a;
            }
        """)
        self._rescan_btn.clicked.connect(lambda: self.rescan_requested.emit(self._path))
        bottom.addWidget(self._rescan_btn)

        remove_btn = QPushButton("REMOVE")
        remove_btn.setCursor(Qt.PointingHandCursor)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: #a1a1aa;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
                color: #ffffff;
                border-color: rgba(255, 255, 255, 0.3);
            }
        """)
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._path))
        bottom.addWidget(remove_btn)

        layout.addLayout(bottom)

    def set_scanning(self, current: int, total: int, filename: str = ""):
        pct = int((current / total * 100)) if total > 0 else 0
        self._progress_bar.setValue(pct)
        self._progress_bar.show()

        clean_name = filename[:32] + "…" if len(filename) > 32 else filename
        status_text = f"● SCANNING ({current}/{total}) {pct}% · {clean_name}" if clean_name else f"● SCANNING ({current}/{total}) {pct}%"
        self._stats_lbl.setText(status_text)
        self._stats_lbl.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 700;")

        self._state_badge.setText(f"● {pct}%")
        self._state_badge.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.18);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.4);
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: 700;
        """)
        self._rescan_btn.setEnabled(False)
        self._rescan_btn.setText("SCANNING…")

    def set_completed(self, file_count: int):
        self._file_count = file_count
        self._progress_bar.setValue(100)
        self._progress_bar.hide()

        self._stats_lbl.setText(f"✓ {file_count} FILES INDEXED · UP TO DATE")
        self._stats_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: 600;")

        self._state_badge.setText("✓ UP TO DATE")
        self._state_badge.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.08);
            color: #d4d4d8;
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 10px;
            font-weight: 700;
        """)
        self._rescan_btn.setEnabled(True)
        self._rescan_btn.setText("RESCAN")


class FolderManager(QWidget):
    folder_added = Signal(str)
    folder_removed = Signal(str)
    rescan_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self._folder_cards: dict[str, FolderCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 24)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────
        badge_lbl = QLabel("▤  INDEXED LOCATIONS")
        badge_lbl.setObjectName("sectionBadge")
        badge_lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: 700; letter-spacing: 2px;")
        root.addWidget(badge_lbl)
        root.addSpacing(6)

        title = QLabel("Folder\nLibrary")
        title.setObjectName("sectionTitle")
        title.setStyleSheet("font-size: 32px; font-weight: 800; color: #ffffff; line-height: 1.1;")
        root.addWidget(title)
        root.addSpacing(24)

        # ── Global Live Activity Banner (shown when indexing is active) ──
        self._activity_banner = QFrame()
        self._activity_banner.setStyleSheet("""
            QFrame {
                background-color: #1e1e20;
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 12px;
                padding: 8px 16px;
            }
        """)
        b_layout = QHBoxLayout(self._activity_banner)
        b_layout.setContentsMargins(12, 6, 12, 6)
        b_layout.setSpacing(10)

        self._banner_dot = QLabel("●")
        self._banner_dot.setStyleSheet("color: #ffffff; font-size: 10px;")
        b_layout.addWidget(self._banner_dot)

        self._banner_lbl = QLabel("Indexing in progress…")
        self._banner_lbl.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 700;")
        b_layout.addWidget(self._banner_lbl, 1)

        self._banner_bar = QProgressBar()
        self._banner_bar.setRange(0, 100)
        self._banner_bar.setFixedWidth(140)
        self._banner_bar.setFixedHeight(4)
        self._banner_bar.setTextVisible(False)
        self._banner_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #ffffff;
                border-radius: 2px;
            }
        """)
        b_layout.addWidget(self._banner_bar)
        self._activity_banner.hide()
        root.addWidget(self._activity_banner)
        root.addSpacing(16)

        # ── Drop zone ─────────────────────────────────────────
        self._drop_zone = DropZone()
        self._drop_zone.folder_dropped.connect(self._add_folder)
        self._drop_zone.folder_browsed.connect(self._add_folder)
        root.addWidget(self._drop_zone)
        root.addSpacing(24)

        # ── Folder cards list ─────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(12)

        # Empty state
        self._empty_lbl = QLabel("No folders added yet. Drop a folder above to start indexing.")
        self._empty_lbl.setStyleSheet("color: #71717a; font-size: 13px; padding: 20px;")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._list_layout.addWidget(self._empty_lbl)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_container)
        root.addWidget(scroll, 1)

    def _add_folder(self, path: str):
        self.folder_added.emit(path)

    def load_folders(self, folders: list[dict]):
        # Clear existing cards
        for card in self._folder_cards.values():
            card.setParent(None)
            card.deleteLater()
        self._folder_cards.clear()

        # Remove stretch & empty label if any
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not folders:
            self._empty_lbl = QLabel("No folders added yet. Drop a folder above to start indexing.")
            self._empty_lbl.setStyleSheet("color: #71717a; font-size: 13px; padding: 20px;")
            self._empty_lbl.setAlignment(Qt.AlignCenter)
            self._list_layout.addWidget(self._empty_lbl)
            self._list_layout.addStretch()
            return

        for f in folders:
            path_str = f.get("path", "")
            count = f.get("file_count", 0)
            card = FolderCard(path_str, file_count=count)
            card.rescan_requested.connect(self.rescan_requested.emit)
            card.remove_requested.connect(self._on_remove)
            self._folder_cards[path_str] = card
            self._list_layout.addWidget(card)

        self._list_layout.addStretch()

    def set_scanning_progress(self, folder_path: str, current: int, total: int, filename: str = ""):
        pct = int((current / total * 100)) if total > 0 else 0
        folder_name = Path(folder_path).name or folder_path

        # Update banner
        self._activity_banner.show()
        clean_file = filename[:28] + "…" if len(filename) > 28 else filename
        self._banner_lbl.setText(f"Scanning {folder_name} ({current}/{total}, {pct}%) · {clean_file}")
        self._banner_bar.setValue(pct)

        # Match card by exact path or resolved path
        resolved_input = str(Path(folder_path).resolve())
        for p_str, card in self._folder_cards.items():
            if p_str == folder_path or str(Path(p_str).resolve()) == resolved_input:
                card.set_scanning(current, total, filename)
                break

    def set_folder_completed(self, folder_path: str, total_files: int):
        self._activity_banner.hide()
        resolved_input = str(Path(folder_path).resolve())
        for p_str, card in self._folder_cards.items():
            if p_str == folder_path or str(Path(p_str).resolve()) == resolved_input:
                card.set_completed(total_files)
                break

    def _on_remove(self, path: str):
        self.folder_removed.emit(path)
        if path in self._folder_cards:
            card = self._folder_cards.pop(path)
            card.setParent(None)
            card.deleteLater()
        if not self._folder_cards:
            self.load_folders([])
