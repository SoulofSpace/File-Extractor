"""
sidebar.py — Claude-Style Navigation Sidebar
Matches user's reference image (media_1789476831952.png):
  • Darker sleek background (#111113) distinct from the #151515 main area
  • "+ New" top pill button (matching Image 1 exactly)
  • Clean vector icons (no emojis): Projects (▤), Artifacts (◈), Code (</>), Customize (◧)
  • Recent Files list directly in sidebar
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

NAV_ITEMS = [
    ("search",      "⌕",    "Search"),
    ("folders",     "▤",    "Folder Library"),
    ("recent",      "◈",    "Recent Files"),
    ("diagnostics", "</>",  "System Status"),
]


class Sidebar(QFrame):
    nav_changed = Signal(str)
    close_requested = Signal()
    add_folder_requested = Signal()
    recent_file_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(240)

        self.setStyleSheet("""
            QFrame#sidebar {
                background-color: #111113;
                border-right: 1px solid rgba(255, 255, 255, 0.07);
            }
        """)

        self._current = "search"
        self._buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 16)
        layout.setSpacing(0)

        # ── Header: App Title + Collapse Button ─────────────────
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 4, 14)

        title = QLabel("FILE XTRACTOR")
        title.setObjectName("brandLogo")
        title.setStyleSheet("""
            QLabel#brandLogo {
                font-family: 'Friday', 'Samsung Sharp Sans', -apple-system, sans-serif;
                font-size: 14px;
                font-weight: 900;
                letter-spacing: 1.5px;
                color: #ffffff;
            }
        """)
        header.addWidget(title)
        header.addStretch()

        collapse_btn = QPushButton("◨")
        collapse_btn.setObjectName("collapseSidebarBtn")
        collapse_btn.setToolTip("Collapse sidebar")
        collapse_btn.setCursor(Qt.PointingHandCursor)
        collapse_btn.setStyleSheet("""
            QPushButton#collapseSidebarBtn {
                background-color: transparent;
                color: #71717a;
                border: none;
                font-size: 15px;
                padding: 4px 6px;
                border-radius: 6px;
            }
            QPushButton#collapseSidebarBtn:hover {
                background-color: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }
        """)
        collapse_btn.clicked.connect(self.close_requested)
        header.addWidget(collapse_btn)

        layout.addLayout(header)

        # ── "+ New" Action Pill Button (Matching Image 1) ───────
        self._new_btn = QPushButton("+  New")
        self._new_btn.setObjectName("sidebarNewBtn")
        self._new_btn.setCursor(Qt.PointingHandCursor)
        self._new_btn.setStyleSheet("""
            QPushButton#sidebarNewBtn {
                background-color: #262628;
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
                padding: 10px 16px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 600;
                text-align: left;
            }
            QPushButton#sidebarNewBtn:hover {
                background-color: #323236;
                border: 1px solid rgba(255, 255, 255, 0.25);
            }
        """)
        self._new_btn.clicked.connect(self.add_folder_requested)
        layout.addWidget(self._new_btn)
        layout.addSpacing(16)

        # ── Navigation Items (Matching Image 1 items & vector icons) ──
        for key, icon, label in NAV_ITEMS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setObjectName("navButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton#navButton {
                    background-color: transparent;
                    color: #a1a1aa;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 12px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    font-size: 13px;
                    font-weight: 500;
                    text-align: left;
                    min-height: 34px;
                }
                QPushButton#navButton:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    color: #ffffff;
                }
                QPushButton#navButton[active="true"] {
                    background-color: rgba(255, 255, 255, 0.10);
                    color: #ffffff;
                    font-weight: 700;
                }
            """)
            btn.clicked.connect(lambda checked=False, k=key: self._on_nav(k))
            self._buttons[key] = btn
            layout.addWidget(btn)
            layout.addSpacing(2)

        layout.addSpacing(22)

        # ── Recent Files Header ────────────────────────────────
        recent_hdr = QLabel("RECENT FILES")
        recent_hdr.setStyleSheet("""
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: #52525b;
            padding: 0 4px;
            margin-bottom: 6px;
        """)
        layout.addWidget(recent_hdr)

        # Scrollable list of recent files
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._recent_container = QWidget()
        self._recent_layout = QVBoxLayout(self._recent_container)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setSpacing(2)
        self._recent_layout.addStretch()

        scroll.setWidget(self._recent_container)
        layout.addWidget(scroll, 1)

        # ── Footer Stats ───────────────────────────────────────
        layout.addSpacing(10)
        self._stat_label = QLabel("0 files indexed")
        self._stat_label.setStyleSheet("""
            font-size: 11px;
            color: #52525b;
            padding: 4px;
        """)
        layout.addWidget(self._stat_label)

        self._set_active("search")

    def _on_nav(self, key: str):
        self._set_active(key)
        self.nav_changed.emit(key)

    def _set_active(self, key: str):
        self._current = key
        for k, btn in self._buttons.items():
            btn.setProperty("active", k == key)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def update_stats(self, file_count: int, folder_count: int):
        self._stat_label.setText(
            f"{file_count:,} files  ·  {folder_count} folders"
        )

    def update_recent_files(self, files: list):
        while self._recent_layout.count() > 1:
            item = self._recent_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for f in files[:8]:
            name = f.filename if hasattr(f, 'filename') else Path(str(f)).name
            path_str = str(f.file_path) if hasattr(f, 'file_path') else str(f)

            btn = QPushButton(name)
            btn.setToolTip(path_str)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #71717a;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 8px;
                    font-size: 12px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.05);
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(lambda checked=False, p=path_str: self.recent_file_clicked.emit(p))
            self._recent_layout.insertWidget(self._recent_layout.count() - 1, btn)
