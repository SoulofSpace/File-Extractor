"""
cyber_scramble.py — Friday Font Kinetic Reveal Title
Uses the user's custom "Friday" font from their laptop:
  • Registered via QFontDatabase from local resources
  • Big bold ALL CAPS: "FILE XTRACTOR"
  • Clean, smooth scramble reveal animation
"""

import os
import random
from pathlib import Path
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontDatabase

# Cipher glyph pool for scrambling
CIPHER_POOL = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#$@%&*"

_font_registered = False

def ensure_friday_font():
    global _font_registered
    if not _font_registered:
        _res_dir = Path(__file__).resolve().parent / "resources"
        _friday_font_path = _res_dir / "Friday.otf"
        if _friday_font_path.exists():
            QFontDatabase.addApplicationFont(str(_friday_font_path))
        _font_registered = True


class CyberScrambleTitle(QWidget):
    """
    Renders the hero title using the custom 'Friday' font in ALL CAPS: "FILE XTRACTOR".
    """
    animation_finished = Signal()

    def __init__(self, target_text: str = "FILE XTRACTOR", sub_text: str = "Search documents, images, code, and text by content", parent=None):
        super().__init__(parent)
        ensure_friday_font()
        self._target = target_text
        self._sub_target = sub_text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        # Main scrambled title with Friday font
        self._title_label = QLabel()
        self._title_label.setObjectName("heroScrambleTitle")
        self._title_label.setAlignment(Qt.AlignCenter)
        self._title_label.setStyleSheet("""
            QLabel#heroScrambleTitle {
                font-family: 'Friday', 'Samsung Sharp Sans', -apple-system, sans-serif;
                font-size: 54px;
                font-weight: normal;
                letter-spacing: 2px;
                color: #ffffff;
            }
        """)
        layout.addWidget(self._title_label)

        # Secondary sub-line
        self._sub_label = QLabel(sub_text)
        self._sub_label.setObjectName("heroSubTitle")
        self._sub_label.setAlignment(Qt.AlignCenter)
        self._sub_label.setStyleSheet("""
            QLabel#heroSubTitle {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: 400;
                letter-spacing: 0.3px;
                color: #8e8e93;
            }
        """)
        layout.addWidget(self._sub_label)

        self._frame = 0
        self._total_scramble_frames = 12
        self._lock_speed = 1.4
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

        self.start_animation()

    def start_animation(self):
        self._frame = 0
        self._timer.start(30)

    def _on_tick(self):
        self._frame += 1
        n = len(self._target)

        if self._frame <= self._total_scramble_frames:
            scrambled = []
            for char in self._target:
                if char == " ":
                    scrambled.append(" ")
                else:
                    scrambled.append(random.choice(CIPHER_POOL))
            display_text = "".join(scrambled)
            self._render_text(display_text, locked_count=0)
            return

        unlocked_frames = self._frame - self._total_scramble_frames
        locked_count = int(unlocked_frames * self._lock_speed)

        if locked_count >= n:
            self._timer.stop()
            self._render_final()
            self.animation_finished.emit()
            return

        result = []
        for i, char in enumerate(self._target):
            if i < locked_count:
                result.append(char)
            elif char == " ":
                result.append(" ")
            else:
                result.append(random.choice(CIPHER_POOL))

        self._render_text("".join(result), locked_count)

    def _render_text(self, text: str, locked_count: int):
        chars_html = []
        for i, ch in enumerate(text):
            if i < locked_count:
                chars_html.append(f'<span style="color: #ffffff;">{ch}</span>')
            else:
                flicker_col = "#d1d1d6" if random.random() > 0.4 else "#636366"
                chars_html.append(f'<span style="color: {flicker_col}; opacity: 0.85;">{ch}</span>')

        self._title_label.setText("".join(chars_html))

    def _render_final(self):
        self._title_label.setText('<span style="color: #ffffff;">FILE XTRACTOR</span>')
