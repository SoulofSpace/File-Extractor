"""
diagnostics_view.py — Portfolio-style system diagnostics view
Golden metric numbers, uppercase labels, glass metric cards
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QScrollArea, QPushButton
)
from PySide6.QtCore import Qt


class MetricCard(QFrame):
    def __init__(self, value: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setMinimumHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(4)

        self._val_lbl = QLabel(value)
        self._val_lbl.setObjectName("metricValue")
        self._val_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._val_lbl)

        lbl = QLabel(label)
        lbl.setObjectName("metricLabel")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

    def set_value(self, value: str):
        self._val_lbl.setText(value)


class DiagnosticsView(QWidget):
    rescan_all_requested = __import__('PySide6.QtCore', fromlist=['Signal']).Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 32, 36, 24)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────
        badge = QLabel("◈  SYSTEM HEALTH")
        badge.setObjectName("sectionBadge")
        root.addWidget(badge)
        root.addSpacing(6)

        title = QLabel("Diagnostics")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        root.addSpacing(28)

        # ── Metric cards grid ─────────────────────────────────
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        self._total_card   = MetricCard("0",   "TOTAL FILES")
        self._indexed_card = MetricCard("0",   "INDEXED")
        self._failed_card  = MetricCard("0",   "FAILED")
        self._folders_card = MetricCard("0",   "FOLDERS")

        grid.addWidget(self._total_card,   0, 0)
        grid.addWidget(self._indexed_card, 0, 1)
        grid.addWidget(self._failed_card,  1, 0)
        grid.addWidget(self._folders_card, 1, 1)

        root.addLayout(grid)
        root.addSpacing(24)

        # ── Actions row ───────────────────────────────────────
        actions = QHBoxLayout()
        rescan_btn = QPushButton("RESCAN ALL FOLDERS")
        rescan_btn.setObjectName("primaryButton")
        rescan_btn.setCursor(Qt.PointingHandCursor)
        rescan_btn.clicked.connect(self.rescan_all_requested)
        actions.addWidget(rescan_btn)
        actions.addStretch()
        root.addLayout(actions)
        root.addSpacing(24)

        # ── Failed files list ─────────────────────────────────
        failed_hdr = QHBoxLayout()
        failed_lbl = QLabel("FAILED FILES")
        failed_lbl.setObjectName("mutedText")
        failed_hdr.addWidget(failed_lbl)
        failed_hdr.addStretch()
        root.addLayout(failed_hdr)
        root.addSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._failed_container = QWidget()
        self._failed_layout = QVBoxLayout(self._failed_container)
        self._failed_layout.setContentsMargins(0, 0, 0, 0)
        self._failed_layout.setSpacing(8)

        self._no_failed_lbl = QLabel("No failed files — all good  ✓")
        self._no_failed_lbl.setObjectName("resultSnippet")
        self._no_failed_lbl.setAlignment(Qt.AlignCenter)
        self._failed_layout.addWidget(self._no_failed_lbl)
        self._failed_layout.addStretch()

        scroll.setWidget(self._failed_container)
        root.addWidget(scroll, 1)

    def update_stats(self, total: int, indexed: int, failed: int, folders: int):
        self._total_card.set_value(str(total))
        self._indexed_card.set_value(str(indexed))
        self._failed_card.set_value(str(failed))
        self._folders_card.set_value(str(folders))

    def load_failed_files(self, files: list):
        # Clear previous
        while self._failed_layout.count() > 1:
            item = self._failed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not files:
            self._no_failed_lbl.show()
            return

        self._no_failed_lbl.hide()
        for f in files:
            card = QFrame()
            card.setObjectName("resultCard")
            cl = QHBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 10)

            err_icon = QLabel("⚠")
            err_icon.setStyleSheet("color: #a1a1aa; font-size: 14px;")
            cl.addWidget(err_icon)
            cl.addSpacing(8)

            path_lbl = QLabel(str(f.file_path) if hasattr(f, 'file_path') else str(f))
            path_lbl.setObjectName("resultPath")
            path_lbl.setWordWrap(False)
            cl.addWidget(path_lbl, 1)

            self._failed_layout.insertWidget(
                self._failed_layout.count() - 1, card
            )
