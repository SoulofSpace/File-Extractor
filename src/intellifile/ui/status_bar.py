"""
status_bar.py — Pure Monochrome Status Bar
Black, White, and Grey palette:
  • Clean white indicator dot
  • Silver/white status text
  • Minimalist white progress bar
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt


class StatusBarWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(10)

        self._dot = QLabel("●")
        self._dot.setObjectName("statusDot")
        self._dot.setStyleSheet("font-size: 8px; color: #ffffff;")
        layout.addWidget(self._dot)

        self._text = QLabel("READY")
        self._text.setObjectName("statusText")
        self._text.setStyleSheet("font-size: 11px; font-weight: 600; color: #a1a1aa; letter-spacing: 1px;")
        layout.addWidget(self._text)

        layout.addStretch()

        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("mutedText")
        self._count_lbl.setStyleSheet("font-size: 11px; color: #71717a;")
        layout.addWidget(self._count_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedWidth(120)
        self._progress.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 2px;
                max-height: 3px;
            }
            QProgressBar::chunk {
                background-color: #ffffff;
                border-radius: 2px;
            }
        """)
        self._progress.hide()
        layout.addWidget(self._progress)

    def set_status(self, message: str):
        self._text.setText(message.upper())

    def set_progress(self, value: int, total: int):
        if total > 0:
            pct = int((value / total) * 100)
            self._progress.setValue(pct)
            self._progress.show()
            self._text.setText(f"INDEXING  {value}/{total}")
            self._dot.setStyleSheet("font-size: 8px; color: #ffffff;")
        else:
            self._progress.hide()
            self._dot.setStyleSheet("font-size: 8px; color: #71717a;")

    def set_idle(self, file_count: int = 0, folder_count: int = 0):
        self._progress.hide()
        self._text.setText("READY")
        self._dot.setStyleSheet("font-size: 8px; color: #ffffff;")
        if file_count > 0:
            self._count_lbl.setText(
                f"{file_count:,} FILES  ·  {folder_count} FOLDERS"
            )

    def set_indexing(self, folder: str = ""):
        self._dot.setStyleSheet("font-size: 8px; color: #ffffff;")
        self._text.setText(f"INDEXING{('  ' + folder) if folder else ''}…")
        self._progress.show()
