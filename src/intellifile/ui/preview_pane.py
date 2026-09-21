"""
preview_pane.py — Portfolio-style file preview drawer
Glass panel, metadata rows, monospace text preview
"""

from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from intellifile.models import DiscoveredFile, get_category_style, classify_video, VIDEO_EXTENSIONS


class PreviewPane(QFrame):
    """Right-side preview drawer — appears when a result card is clicked."""
    open_requested = Signal(str)
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewDrawer")
        self.setFixedWidth(300)
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 24, 20, 24)
        root.setSpacing(16)

        # ── Header row ────────────────────────────────────────
        header_row = QHBoxLayout()

        header_lbl = QLabel("PREVIEW")
        header_lbl.setObjectName("mutedText")
        header_row.addWidget(header_lbl)
        header_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("iconTextButton")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self._close)
        header_row.addWidget(close_btn)

        root.addLayout(header_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        # ── File title ────────────────────────────────────────
        self._title_lbl = QLabel("—")
        self._title_lbl.setObjectName("previewTitle")
        self._title_lbl.setWordWrap(True)
        root.addWidget(self._title_lbl)

        # ── Category badge ────────────────────────────────────
        self._badge_lbl = QLabel("")
        self._badge_lbl.setObjectName("badgeLabel")
        root.addWidget(self._badge_lbl)

        # ── Metadata rows ─────────────────────────────────────
        self._meta_widget = QWidget()
        meta_layout = QVBoxLayout(self._meta_widget)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(6)

        self._meta_rows: dict[str, QLabel] = {}
        for key in ["SIZE", "TYPE", "LOCATION", "STATUS"]:
            row = QFrame()
            row.setObjectName("previewMetaRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 8, 12, 8)
            row_layout.setSpacing(12)

            key_lbl = QLabel(key)
            key_lbl.setObjectName("previewMetaKey")
            key_lbl.setFixedWidth(60)
            row_layout.addWidget(key_lbl)

            val_lbl = QLabel("—")
            val_lbl.setObjectName("previewMetaVal")
            val_lbl.setWordWrap(True)
            row_layout.addWidget(val_lbl, 1)

            self._meta_rows[key] = val_lbl
            meta_layout.addWidget(row)

        root.addWidget(self._meta_widget)

        # ── Text preview ──────────────────────────────────────
        text_lbl = QLabel("CONTENT PREVIEW")
        text_lbl.setObjectName("mutedText")
        root.addWidget(text_lbl)

        self._text_edit = QTextEdit()
        self._text_edit.setObjectName("previewText")
        self._text_edit.setReadOnly(True)
        self._text_edit.setMinimumHeight(140)
        root.addWidget(self._text_edit, 1)

        # ── Open button ───────────────────────────────────────
        self._open_btn = QPushButton("OPEN FILE  →")
        self._open_btn.setObjectName("primaryButton")
        self._open_btn.setCursor(Qt.PointingHandCursor)
        self._open_btn.clicked.connect(self._open_file)
        root.addWidget(self._open_btn)

        self._current_path: str = ""

    def show_file(self, file: object):
        if isinstance(file, dict):
            file_path = str(file.get("path", ""))
            filename = str(file.get("filename", Path(file_path).name if file_path else "Untitled"))
            file_type = str(file.get("file_type", "document"))
            extracted_text = file.get("extracted_text", "")
            ocr_text = file.get("ocr_text", "")
            status = file.get("indexing_status", "indexed")
            ext = str(file.get("extension", "")).lower()
            size_bytes = file.get("size_bytes", 0)
        else:
            file_path = str(getattr(file, "file_path", getattr(file, "path", "")))
            filename = str(getattr(file, "filename", Path(file_path).name if file_path else "Untitled"))
            file_type = str(getattr(file, "file_type", "document"))
            extracted_text = getattr(file, "extracted_text", "")
            ocr_text = getattr(file, "ocr_text", "")
            status = getattr(file, "status", getattr(file, "indexing_status", "indexed"))
            ext = str(getattr(file, "extension", "")).lower()
            size_bytes = getattr(file, "size", 0)

        self._current_path = file_path
        self._title_lbl.setText(filename)

        # Video classification
        if ext in VIDEO_EXTENSIONS:
            subtype, v_label = classify_video(file_path, size_bytes)
            type_label = v_label.upper()
            badge_text = f"🎬 {type_label}" if subtype == "Movie" else "▶ VIDEO"
            cat_key = "Movie" if subtype == "Movie" else "Video"
        else:
            type_label = file_type.upper()
            badge_text = f"▤ {type_label}"
            cat_key = file_type

        style = get_category_style(cat_key)
        self._badge_lbl.setText(badge_text)
        self._badge_lbl.setStyleSheet(
            f"background-color: {style.get('bg', 'rgba(255,255,255,0.08)')};"
            f"color: {style.get('fg', '#ffffff')};"
            f"border-radius: 980px; padding: 3px 12px;"
            f"font-size: 9px; font-weight: 700; letter-spacing: 1.5px;"
        )

        # Size calculation
        try:
            if not size_bytes and file_path and Path(file_path).exists():
                size_bytes = Path(file_path).stat().st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 ** 2:
                size_str = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 ** 3:
                size_str = f"{size_bytes / (1024**2):.1f} MB"
            else:
                size_str = f"{size_bytes / (1024**3):.2f} GB"
        except Exception:
            size_str = "Unknown"

        self._meta_rows["SIZE"].setText(size_str)
        self._meta_rows["TYPE"].setText(type_label)
        self._meta_rows["LOCATION"].setText(str(Path(file_path).parent if file_path else "—"))
        self._meta_rows["STATUS"].setText(
            "✓ INDEXED" if status == "indexed" else "PENDING"
        )

        # Content preview (Digital text, OCR text, or both)
        preview_parts = []
        if extracted_text and extracted_text.strip():
            preview_parts.append(f"--- DIGITAL CONTENT ---\n{extracted_text.strip()[:1000]}")
        if ocr_text and ocr_text.strip():
            preview_parts.append(f"--- OCR EXTRACTED TEXT ---\n{ocr_text.strip()[:1000]}")

        if preview_parts:
            self._text_edit.setPlainText("\n\n".join(preview_parts))
        else:
            self._text_edit.setPlainText("No text extracted (media file, archive, or non-text document)")

        self.show()

    def _close(self):
        self.hide()
        self.closed.emit()

    def _open_file(self):
        if self._current_path:
            self.open_requested.emit(self._current_path)
