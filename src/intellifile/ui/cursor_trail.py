"""
cursor_trail.py — Monochrome File-Tag Cursor Trail Effect
Strict Black, White, and Grey palette:
  • Normal OS cursor is untouched (no icon at cursor pointer)
  • Trail spawns floating mini file-type tags (PDF, JPG, DOC, TXT, PNG, ZIP, CODE, RAW)
    and silver/white stardust particles drifting smoothly behind cursor movement
"""

import math
import random
from PySide6.QtWidgets import QWidget, QApplication, QPushButton, QLineEdit, QTextEdit, QAbstractButton
from PySide6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF, QObject, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class FileTagNode:
    __slots__ = ('x', 'y', 'tag', 'alpha', 'scale', 'vx', 'vy')

    def __init__(self, x: float, y: float, tag: str):
        self.x = x
        self.y = y
        self.tag = tag
        self.alpha = 240
        self.scale = 1.0
        self.vx = random.uniform(-0.35, 0.35)
        self.vy = random.uniform(-0.4, 0.2)  # Gentle upward float


class DustParticle:
    __slots__ = ('x', 'y', 'radius', 'alpha', 'color', 'vx', 'vy')

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.radius = random.uniform(1.5, 3.5)
        self.alpha = random.randint(160, 230)
        self.color = QColor(random.choice([255, 230, 200, 180]), random.choice([255, 230, 200, 180]), random.choice([255, 230, 200, 180]))
        self.vx = random.uniform(-0.4, 0.4)
        self.vy = random.uniform(-0.4, 0.4)


class CursorTrail(QWidget):
    """
    Transparent overlay rendering floating monochrome file-tag pills
    and stardust particles trailing behind cursor movement.
    """
    FILE_TAGS = ["PDF", "JPG", "DOC", "TXT", "PNG", "ZIP", "CODE", "RAW", "CSV", "MP4"]

    def __init__(self, parent_window):
        super().__init__(parent_window)

        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.raise_()

        # Coordinates
        self.mx = 0.0
        self.my = 0.0
        self.last_spawn_x = 0.0
        self.last_spawn_y = 0.0

        self.tag_nodes: list[FileTagNode] = []
        self.dust_particles: list[DustParticle] = []
        self._counter = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        if parent_window:
            self.setGeometry(parent_window.rect())
            parent_window.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Resize:
            self.setGeometry(self.parent().rect())
        return False

    def update_cursor_pos(self, x: float, y: float, is_interactive: bool = False):
        self.mx = x
        self.my = y

    def _tick(self):
        dist = math.hypot(self.mx - self.last_spawn_x, self.my - self.last_spawn_y)
        self._counter += 1

        # Spawn floating file tag every few pixels of mouse movement
        if dist > 22.0 or (dist > 6.0 and self._counter % 6 == 0):
            self.last_spawn_x = self.mx
            self.last_spawn_y = self.my

            if len(self.tag_nodes) < 16:
                tag = random.choice(self.FILE_TAGS)
                node = FileTagNode(self.mx + random.uniform(-6, 6), self.my + random.uniform(6, 14), tag)
                self.tag_nodes.append(node)

            # Spawn a few stardust particles
            if len(self.dust_particles) < 25:
                for _ in range(2):
                    self.dust_particles.append(DustParticle(self.mx, self.my))

        # Update file tag nodes
        survived_tags = []
        for node in self.tag_nodes:
            node.x += node.vx
            node.y += node.vy
            node.alpha -= 7
            node.scale *= 0.97
            if node.alpha > 12 and node.scale > 0.35:
                survived_tags.append(node)
        self.tag_nodes = survived_tags

        # Update dust particles
        survived_dust = []
        for p in self.dust_particles:
            p.x += p.vx
            p.y += p.vy
            p.alpha -= 9
            p.radius *= 0.95
            if p.alpha > 15 and p.radius > 0.4:
                survived_dust.append(p)
        self.dust_particles = survived_dust

        self.update()

    def paintEvent(self, event):
        if not self.tag_nodes and not self.dust_particles:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # ── 1. Draw floating monochrome stardust ─────────────────────
        painter.setPen(Qt.NoPen)
        for p in self.dust_particles:
            c = QColor(p.color)
            c.setAlpha(p.alpha)
            painter.setBrush(QBrush(c))
            painter.drawEllipse(
                int(p.x - p.radius), int(p.y - p.radius),
                int(p.radius * 2), int(p.radius * 2)
            )

        # ── 2. Draw floating monochrome file-tag pills ───────────────
        font = QFont("Segoe UI", 7, QFont.Bold)
        painter.setFont(font)

        for node in self.tag_nodes:
            painter.save()
            painter.translate(node.x, node.y)
            painter.scale(node.scale, node.scale)

            # Pill container dimensions
            pill_w = 26.0
            pill_h = 13.0
            rect = QRectF(-pill_w / 2, -pill_h / 2, pill_w, pill_h)

            # Semi-transparent dark background + crisp white/silver border
            bg_col = QColor(15, 15, 18, int(node.alpha * 0.85))
            border_col = QColor(255, 255, 255, int(node.alpha * 0.65))

            painter.setPen(QPen(border_col, 1.0))
            painter.setBrush(QBrush(bg_col))
            painter.drawRoundedRect(rect, 4.0, 4.0)

            # Crisp white text
            text_col = QColor(255, 255, 255, node.alpha)
            painter.setPen(text_col)
            painter.drawText(rect, Qt.AlignCenter, node.tag)

            painter.restore()

        painter.end()


class GlobalMouseTracker(QObject):
    """
    Captures mouse moves across all widgets and updates the trail and background.
    """
    def __init__(self, cursor_trail: CursorTrail, space_bg):
        super().__init__()
        self.cursor_trail = cursor_trail
        self.space_bg = space_bg

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.MouseMove, QEvent.HoverMove):
            gpos = event.globalPosition().toPoint()
            win = self.cursor_trail.window()
            if win:
                local_pos = win.mapFromGlobal(gpos)
                x = float(local_pos.x())
                y = float(local_pos.y())

                self.cursor_trail.update_cursor_pos(x, y)
                if self.space_bg:
                    self.space_bg.update_mouse(x, y)

        return False
