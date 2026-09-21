"""
search_view.py — FILE XTRACTOR Main View
Matches Claude reference & user specifications:
  • Base canvas color: #151515 (exact user swatch)
  • Friday font title: "FILE XTRACTOR"
  • 60fps smooth downward-extending search capsule on hover/focus
  • Suggestion chips with curved edges & vector icons (NO emojis)
  • Fluid results viewport with clean preview cards
"""

from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QFrame, QSizePolicy, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QVariantAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QFont, QColor

from intellifile.models import DiscoveredFile, get_category_style, classify_video, VIDEO_EXTENSIONS
from intellifile.ui.cyber_scramble import CyberScrambleTitle

CATEGORIES = [
    ("ALL",       "All"),
    ("DOCUMENT",  "Documents"),
    ("IMAGE",     "Images (OCR)"),
    ("VIDEO",     "Videos & Movies"),
    ("CODE",      "Code"),
    ("AUDIO",     "Audio"),
    ("ARCHIVE",   "Archives"),
]

# Vector-style icon tags (NO emojis)
SAMPLE_CHIPS = [
    ("Python code",     "</> Python Code"),
    ("resume PDF",       "▤ Resumes & PDFs"),
    ("meeting notes",    "✎ Meeting Notes"),
    ("project invoices", "☷ Invoices"),
    ("design assets",    "⊞ Design Assets"),
]


class ExpandableSearchCard(QFrame):
    """
    Claude-inspired floating search capsule that smoothly expands downward at 60fps
    from 56px to 130px when hovered or focused, revealing bottom controls.
    """
    search_triggered = Signal()

    COLLAPSED_HEIGHT = 56
    EXPANDED_HEIGHT = 132

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("searchCapsule")
        self.setFixedHeight(self.COLLAPSED_HEIGHT)
        self.setMaximumWidth(780)

        self.setStyleSheet("""
            QFrame#searchCapsule {
                background-color: #1e1e20;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 20px;
            }
            QFrame#searchCapsule:focus-within {
                border: 1.5px solid rgba(255, 255, 255, 0.45);
                background-color: #222226;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 12)
        layout.setSpacing(10)

        # ── Top Row: Search Icon + Text Input ─────────────────
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        top_row.setContentsMargins(0, 0, 0, 0)

        search_icon = QLabel("⌕")
        search_icon.setStyleSheet("color: rgba(255, 255, 255, 0.45); font-size: 22px; font-weight: bold;")
        top_row.addWidget(search_icon)

        self.input = QLineEdit()
        self.input.setObjectName("searchCapsuleInput")
        self.input.setPlaceholderText("How can I help you find files today? (e.g. quarterly report, python script)...")
        self.input.setStyleSheet("""
            QLineEdit#searchCapsuleInput {
                background-color: transparent;
                border: none;
                color: #ffffff;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 15px;
                font-weight: 400;
                padding: 4px 0px;
            }
            QLineEdit#searchCapsuleInput::placeholder {
                color: rgba(255, 255, 255, 0.35);
            }
        """)
        self.input.returnPressed.connect(self.search_triggered)
        top_row.addWidget(self.input, 1)

        layout.addLayout(top_row)

        # ── Bottom Row: Revealed on Expansion (Claude-style) ──
        self.bottom_bar = QWidget()
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(10)

        # Left filter tag
        self.mode_tag = QLabel("All Content")
        self.mode_tag.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.06);
            color: #a1a1aa;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
        """)
        bottom_layout.addWidget(self.mode_tag)
        bottom_layout.addStretch()

        # Keyboard hint
        hint = QLabel("↵ Enter to search")
        hint.setStyleSheet("color: #71717a; font-size: 11px;")
        bottom_layout.addWidget(hint)

        # Search submit pill button
        self.submit_btn = QPushButton("Search  →")
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                border: none;
                border-radius: 12px;
                padding: 7px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #e4e4e7;
            }
        """)
        self.submit_btn.clicked.connect(self.search_triggered)
        bottom_layout.addWidget(self.submit_btn)

        # Opacity effect for smooth fade
        self.opacity_effect = QGraphicsOpacityEffect(self.bottom_bar)
        self.opacity_effect.setOpacity(0.0)
        self.bottom_bar.setGraphicsEffect(self.opacity_effect)
        self.bottom_bar.hide()

        layout.addWidget(self.bottom_bar)

        # ── 60fps Smooth Extension Animation ──────────────────
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_step)

        self._is_expanded = False

    def enterEvent(self, event):
        super().enterEvent(event)
        self.expand()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        # Collapse only if input is not focused and has no text
        if not self.input.hasFocus() and not self.input.text().strip():
            self.collapse()

    def expand(self):
        if self._is_expanded:
            return
        self._is_expanded = True
        self.bottom_bar.show()

        self._anim.stop()
        self._anim.setStartValue(self.height())
        self._anim.setEndValue(self.EXPANDED_HEIGHT)
        self._anim.start()

    def collapse(self):
        if not self._is_expanded:
            return
        self._is_expanded = False

        self._anim.stop()
        self._anim.setStartValue(self.height())
        self._anim.setEndValue(self.COLLAPSED_HEIGHT)
        self._anim.start()

    def _on_anim_step(self, val):
        self.setFixedHeight(int(val))
        # Fade bottom bar proportionally
        progress = (val - self.COLLAPSED_HEIGHT) / (self.EXPANDED_HEIGHT - self.COLLAPSED_HEIGHT)
        progress = max(0.0, min(1.0, progress))
        self.opacity_effect.setOpacity(progress)
        if progress <= 0.05 and not self._is_expanded:
            self.bottom_bar.hide()


class ResultCard(QFrame):
    clicked = Signal(object)
    open_requested = Signal(str)

    def __init__(self, file: object, parent=None):
        super().__init__(parent)
        self.setObjectName("resultCard")
        self.file = file
        self.setCursor(Qt.PointingHandCursor)

        # Safely extract attributes from dict or model object
        if isinstance(file, dict):
            self.file_path = str(file.get("path", ""))
            self.filename = str(file.get("filename", Path(self.file_path).name if self.file_path else "Untitled"))
            self.file_type = str(file.get("file_type", file.get("extension", "file")))
            self.extracted_text = file.get("extracted_text", "")
            self.ocr_text = file.get("ocr_text", "")
            self.score = file.get("rank") or file.get("score")
            self.snippet_raw = file.get("snippet", "")
            self.extension = str(file.get("extension", "")).lower()
            self.size_bytes = file.get("size_bytes", 0)
            self.ai_badge = file.get("ai_badge", "")
            self.ai_explanation = file.get("ai_explanation", "")
        else:
            self.file_path = str(getattr(file, "file_path", getattr(file, "path", "")))
            self.filename = str(getattr(file, "filename", Path(self.file_path).name if self.file_path else "Untitled"))
            self.file_type = str(getattr(file, "file_type", getattr(file, "extension", "file")))
            self.extracted_text = getattr(file, "extracted_text", "")
            self.ocr_text = getattr(file, "ocr_text", "")
            self.score = getattr(file, "score", None)
            self.snippet_raw = ""
            self.extension = str(getattr(file, "extension", "")).lower()
            self.size_bytes = getattr(file, "size", 0)
            self.ai_badge = getattr(file, "ai_badge", "")
            self.ai_explanation = getattr(file, "ai_explanation", "")

        self.setStyleSheet("""
            QFrame#resultCard {
                background-color: #1e1e20;
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 14px;
            }
            QFrame#resultCard:hover {
                background-color: #242428;
                border: 1px solid rgba(255, 255, 255, 0.25);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        # ── Top row: filename + badges + Open button ──────────
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        title = QLabel(self.filename)
        title.setObjectName("resultTitle")
        title.setWordWrap(False)
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff;")
        top_row.addWidget(title, 1)

        # AI Agent Match Badge (High prominence white badge)
        if self.ai_badge:
            ai_lbl = QLabel(self.ai_badge)
            ai_lbl.setStyleSheet("""
                background-color: #ffffff;
                color: #000000;
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 0.5px;
            """)
            top_row.addWidget(ai_lbl)

        # Video / Movie Classification Badge
        if self.extension in VIDEO_EXTENSIONS:
            subtype, v_label = classify_video(self.file_path, self.size_bytes)
            v_badge = QLabel(f"🎬 {v_label.upper()}" if subtype == "Movie" else "▶ VIDEO")
            v_badge.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.16);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.35);
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 700;
            """)
            top_row.addWidget(v_badge)

        # OCR Match Badge
        if self.ocr_text and not self.ai_badge:
            ocr_badge = QLabel("⌕ OCR TEXT")
            ocr_badge.setStyleSheet("""
                background-color: rgba(255, 255, 255, 0.10);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 700;
            """)
            top_row.addWidget(ocr_badge)

        # Category badge (Clean monochrome vector tag)
        badge = QLabel(f"▤ {self.file_type.upper().lstrip('.')}")
        badge.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.06);
            color: #d4d4d8;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 6px;
            padding: 3px 8px;
            font-size: 10px;
            font-weight: 600;
        """)
        top_row.addWidget(badge)

        # Dedicated Open Button right on the card
        open_btn = QPushButton("Open ↗")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.setToolTip(f"Open {self.filename} in default application")
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #000000;
                border: none;
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #e4e4e7;
            }
        """)
        open_btn.clicked.connect(lambda: self.open_requested.emit(self.file_path))
        top_row.addWidget(open_btn)

        layout.addLayout(top_row)

        # AI Explanation if available
        if self.ai_explanation:
            ai_exp_lbl = QLabel(f"↳ {self.ai_explanation}")
            ai_exp_lbl.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 600;")
            layout.addWidget(ai_exp_lbl)

        # Snippet (Native text, FTS match, or OCR text)
        snippet_content = ""
        if self.snippet_raw:
            snippet_content = str(self.snippet_raw)
        elif self.extracted_text:
            snippet_content = str(self.extracted_text)[:180].replace("\n", " ").strip()
        elif self.ocr_text:
            snippet_content = f"OCR: {str(self.ocr_text)[:180].replace(chr(10), ' ').strip()}"

        if snippet_content:
            if len(snippet_content) > 180 and not snippet_content.endswith("…"):
                snippet_content += "…"
            snippet = QLabel(snippet_content)
            snippet.setWordWrap(True)
            snippet.setStyleSheet("color: #a1a1aa; font-size: 12px; line-height: 1.5;")
            layout.addWidget(snippet)

        # Path
        path_label = QLabel(self.file_path)
        path_label.setWordWrap(False)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_label.setStyleSheet("color: #71717a; font-size: 11px;")
        layout.addWidget(path_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.file)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.open_requested.emit(self.file_path)
        super().mouseDoubleClickEvent(event)


class SearchView(QWidget):
    search_requested = Signal(str, str)
    file_selected = Signal(object)
    file_opened = Signal(str)
    toggle_sidebar_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("page")
        self._current_category = "ALL"
        self._hero_mode = True

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 20, 40, 20)
        root.setSpacing(0)

        # ── Top Bar ────────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 12)

        self._sidebar_toggle_btn = QPushButton("☰  Menu")
        self._sidebar_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._sidebar_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
        """)
        self._sidebar_toggle_btn.clicked.connect(self.toggle_sidebar_requested)
        self._sidebar_toggle_btn.hide()
        top_bar.addWidget(self._sidebar_toggle_btn)
        top_bar.addStretch()

        self._home_btn = QPushButton("← New Search")
        self._home_btn.setCursor(Qt.PointingHandCursor)
        self._home_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.06);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 10px;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
        """)
        self._home_btn.clicked.connect(self.reset_to_home)
        self._home_btn.hide()
        top_bar.addWidget(self._home_btn)

        root.addLayout(top_bar)

        # ── Hero Title Section with Friday Font ────────────────
        self._hero_container = QWidget()
        hero_vbox = QVBoxLayout(self._hero_container)
        hero_vbox.setContentsMargins(0, 30, 0, 24)
        hero_vbox.setSpacing(10)
        hero_vbox.setAlignment(Qt.AlignCenter)

        # Custom Friday font kinetic reveal title
        self._scramble_title = CyberScrambleTitle("FILE XTRACTOR", "Search documents, images, code, and text by content")
        hero_vbox.addWidget(self._scramble_title)

        root.addWidget(self._hero_container)

        # ── Expandable Search Card (Smooth 60fps extension) ───
        self._search_card_wrapper = QWidget()
        search_wrapper_layout = QVBoxLayout(self._search_card_wrapper)
        search_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        search_wrapper_layout.setAlignment(Qt.AlignCenter)

        self._search_card = ExpandableSearchCard()
        self._search_card.search_triggered.connect(self._on_search)
        search_wrapper_layout.addWidget(self._search_card)

        root.addWidget(self._search_card_wrapper)

        # ── Suggestion Chips with Curved Edges & Vector Icons ──
        self._quick_widget = QWidget()
        quick_layout = QVBoxLayout(self._quick_widget)
        quick_layout.setContentsMargins(0, 18, 0, 0)
        quick_layout.setAlignment(Qt.AlignCenter)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(10)
        chips_row.setAlignment(Qt.AlignCenter)

        for q, label in SAMPLE_CHIPS:
            chip = QPushButton(label)
            chip.setCursor(Qt.PointingHandCursor)
            # Curved edges (14px border-radius) matching user specification
            chip.setStyleSheet("""
                QPushButton {
                    background-color: #1e1e20;
                    color: #d4d4d8;
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 14px;
                    padding: 9px 18px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #26262a;
                    border: 1px solid rgba(255, 255, 255, 0.28);
                    color: #ffffff;
                }
            """)
            chip.clicked.connect(lambda checked=False, query=q: self._quick_query(query))
            chips_row.addWidget(chip)

        quick_layout.addLayout(chips_row)
        root.addWidget(self._quick_widget)

        # ── Results Area (Matches #151515 theme) ────────────────
        self._results_box = QFrame()
        self._results_box.setObjectName("resultsContainerBox")
        self._results_box.setStyleSheet("""
            QFrame#resultsContainerBox {
                background-color: #1a1a1c;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 18px;
                padding: 14px;
            }
        """)
        self._results_box.hide()

        results_box_layout = QVBoxLayout(self._results_box)
        results_box_layout.setContentsMargins(14, 14, 14, 14)
        results_box_layout.setSpacing(10)

        # Category pills
        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)
        self._pill_btns: dict[str, QPushButton] = {}
        for cat_key, cat_label in CATEGORIES:
            btn = QPushButton(cat_label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 0.04);
                    color: #a1a1aa;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 10px;
                    padding: 6px 14px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.08);
                    color: #ffffff;
                }
                QPushButton[selected="true"] {
                    background-color: rgba(255, 255, 255, 0.16);
                    color: #ffffff;
                    border: 1px solid #ffffff;
                }
            """)
            btn.clicked.connect(lambda checked=False, c=cat_key: self._on_cat(c))
            self._pill_btns[cat_key] = btn
            pills_row.addWidget(btn)
        pills_row.addStretch()

        self._result_count_lbl = QLabel("0 results")
        self._result_count_lbl.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 700;")
        pills_row.addWidget(self._result_count_lbl)
        results_box_layout.addLayout(pills_row)

        # Scrollable result cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 4, 0, 0)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch()

        scroll.setWidget(self._results_container)
        results_box_layout.addWidget(scroll, 1)

        root.addWidget(self._results_box, 1)

        self._set_pill("ALL")
        self._result_cards: list[ResultCard] = []

    def set_menu_button_visible(self, visible: bool):
        self._sidebar_toggle_btn.setVisible(visible)

    def _on_search(self):
        q = self._search_card.input.text().strip()
        if not q:
            return

        self._enter_results_mode()
        self.search_requested.emit(q, self._current_category)

    def _quick_query(self, q: str):
        self._search_card.input.setText(q)
        self._search_card.expand()
        self._on_search()

    def _on_cat(self, cat: str):
        self._set_pill(cat)
        self._current_category = cat
        q = self._search_card.input.text().strip()
        if q:
            self.search_requested.emit(q, cat)

    def _set_pill(self, cat: str):
        for k, btn in self._pill_btns.items():
            btn.setProperty("selected", k == cat)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _enter_results_mode(self):
        self._hero_mode = False
        self._hero_container.hide()
        self._quick_widget.hide()
        self._results_box.show()
        self._home_btn.show()

    def reset_to_home(self):
        self._hero_mode = True
        self._results_box.hide()
        self._home_btn.hide()
        self._hero_container.show()
        self._quick_widget.show()
        self._search_card.collapse()
        self._scramble_title.start_animation()

    def display_results(self, files: list):
        self._enter_results_mode()

        for card in self._result_cards:
            card.setParent(None)
            card.deleteLater()
        self._result_cards.clear()

        count = len(files)
        self._result_count_lbl.setText(f"{count} {'file' if count == 1 else 'files'} found")

        if not files:
            no_result = QLabel("No files matched your search. Try different keywords or browse folders.")
            no_result.setAlignment(Qt.AlignCenter)
            no_result.setStyleSheet("color: #71717a; font-size: 14px; padding: 40px;")
            self._results_layout.insertWidget(0, no_result)
            return

        for i, f in enumerate(files):
            card = ResultCard(f)
            card.clicked.connect(self.file_selected)
            card.open_requested.connect(self.file_opened.emit)
            self._results_layout.insertWidget(i, card)
            self._result_cards.append(card)
