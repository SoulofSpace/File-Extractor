"""
space_background.py — Minimalist Interactive Background
Matches user's exact swatch (#151515) with subtle, non-intrusive ambient life:
  • Solid base color: #151515 (exact RGB 21, 21, 21 from user image)
  • Minimal, quiet, elegant stardust particles (tiny 0.8px – 1.8px)
  • No giant orbs, no thick rings, no visual clutter
  • Faint, delicate constellation filaments that appear only near the cursor
  • Gentle upward drift responding smoothly to cursor movement
"""

import math
import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QRadialGradient


class StardustParticle:
    __slots__ = ('x', 'y', 'z', 'vx', 'vy', 'radius', 'base_alpha', 'twinkle', 'twinkle_speed')

    def __init__(self, w: float, h: float):
        self.reset(w, h, random_y=True)

    def reset(self, w: float, h: float, random_y: bool = False):
        self.x = random.uniform(0, max(w, 200))
        self.y = random.uniform(0, max(h, 200)) if random_y else h + random.uniform(10, 30)
        self.z = random.uniform(0.4, 1.4)
        self.vx = random.uniform(-0.12, 0.12) * self.z
        self.vy = -random.uniform(0.18, 0.45) * self.z  # Gentle, calm upward drift
        # Tiny subtle specks — NO giant circles
        self.radius = max(0.8, random.uniform(0.9, 1.8) * self.z)
        self.base_alpha = random.randint(35, 85)
        self.twinkle = random.uniform(0, math.pi * 2)
        self.twinkle_speed = random.uniform(0.02, 0.05)


class InteractiveSpaceBackground(QWidget):
    """
    Minimalist interactive canvas covering the entire background of the application.
    Uses exact swatch color #151515 with subtle, executive stardust motes.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("spaceBackground")

        self._t = 0.0
        self._particles: list[StardustParticle] = []
        self._num_particles = 95  # Moderate, uncluttered count

        self._mx = -1000.0
        self._my = -1000.0
        self._last_mx = None
        self._last_my = None
        self._impulse_x = 0.0
        self._impulse_y = 0.0

        self._init_particles(1280, 800)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _init_particles(self, w: float, h: float):
        self._particles = [StardustParticle(w, h) for _ in range(self._num_particles)]

    def update_mouse(self, mx: float, my: float):
        if self._last_mx is not None and self._last_my is not None:
            dx = mx - self._last_mx
            dy = my - self._last_my
            # Gentle, smooth impulse
            self._impulse_x = dx * 0.08
            self._impulse_y = dy * 0.10

        self._mx = mx
        self._my = my
        self._last_mx = mx
        self._last_my = my

    def _tick(self):
        self._t += 0.01

        w = float(self.width() or 1280)
        h = float(self.height() or 800)

        # Decay impulse smoothly
        self._impulse_x *= 0.90
        self._impulse_y *= 0.90

        for p in self._particles:
            p.twinkle += p.twinkle_speed

            # Subtle mouse repulsion
            d_mouse = math.hypot(p.x - self._mx, p.y - self._my)
            repel_x = 0.0
            repel_y = 0.0
            if d_mouse < 90 and d_mouse > 0:
                factor = (1.0 - (d_mouse / 90.0)) * 0.8
                repel_x = ((p.x - self._mx) / d_mouse) * factor
                repel_y = ((p.y - self._my) / d_mouse) * factor

            p.x += p.vx + self._impulse_x * p.z * 0.2 + repel_x
            p.y += p.vy + self._impulse_y * p.z * 0.25 + repel_y

            # Screen wrap
            if p.y < -15:
                p.y = h + 10
                p.x = random.uniform(0, w)
            elif p.y > h + 15:
                p.y = -10
                p.x = random.uniform(0, w)

            if p.x < -15:
                p.x = w + 10
            elif p.x > w + 15:
                p.x = -10

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # ── 1. User's exact swatch grey (#151515) ───────────────────
        painter.fillRect(self.rect(), QColor(21, 21, 21))

        # ── 2. Extremely soft, minimal ambient vignette ─────────────
        # Gentle center brightening (subtle depth without popping)
        grad = QRadialGradient(w * 0.5, h * 0.45, max(w, h) * 0.6)
        grad.setColorAt(0.0, QColor(28, 28, 30, 80))
        grad.setColorAt(1.0, QColor(21, 21, 21, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        painter.drawRect(self.rect())

        # ── 3. Faint delicate filaments near cursor ─────────────────
        if self._mx > 0 and self._my > 0:
            nearby = [p for p in self._particles if math.hypot(p.x - self._mx, p.y - self._my) < 80]
            for i in range(len(nearby)):
                for j in range(i + 1, len(nearby)):
                    dist = math.hypot(nearby[i].x - nearby[j].x, nearby[i].y - nearby[j].y)
                    if dist < 60:
                        alpha = int((1.0 - (dist / 60.0)) * 40)
                        painter.setPen(QPen(QColor(255, 255, 255, alpha), 0.8))
                        painter.drawLine(int(nearby[i].x), int(nearby[i].y),
                                         int(nearby[j].x), int(nearby[j].y))

        # ── 4. Render minimal stardust specks (NO giant circles) ────
        painter.setPen(Qt.NoPen)
        for p in self._particles:
            twinkle_val = (math.sin(p.twinkle) + 1.0) * 0.5
            alpha = int(p.base_alpha * (0.6 + 0.4 * twinkle_val))
            alpha = max(15, min(120, alpha))

            # Crisp, tiny stardust dot
            painter.setBrush(QBrush(QColor(240, 240, 245, alpha)))
            painter.drawEllipse(
                int(p.x - p.radius), int(p.y - p.radius),
                max(1, int(p.radius * 2)), max(1, int(p.radius * 2))
            )

        painter.end()
