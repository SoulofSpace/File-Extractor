"""
styles.py — Pure Monochrome Design System (Black, White, Grey)
Strict monochrome palette:
  • Background: #060608 / #0c0c0e
  • Surfaces & Cards: rgba(255, 255, 255, 0.04), border rgba(255, 255, 255, 0.12)
  • Primary Buttons: Pure White (#ffffff) with Pitch Black (#000000) text
  • Secondary Buttons: Glass Grey (rgba(255, 255, 255, 0.08)), text #ffffff
  • Typography: Samsung Sharp Sans / Segoe UI in Pure White (#ffffff) and Greys
  • NO colors (no yellow, no blue, no red, no cyan)
"""

DARK_STYLESHEET = """
/* ===================================================================
   PURE MONOCHROME DESIGN SYSTEM — BLACK, WHITE & GREY
   =================================================================== */

/* ── GLOBAL BASE ── */
QMainWindow {
    background-color: #151515;
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

QWidget {
    background-color: transparent;
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
}

QLabel#heroTitle, QLabel#sectionTitle, QLabel#brandLogo, QPushButton#primaryButton {
    font-family: 'Friday', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-weight: 900;
}

/* ── SIDEBAR / NAV ── */
QFrame#sidebar {
    background-color: #111113;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

QLabel#brandLogo {
    font-size: 14px;
    font-weight: 900;
    letter-spacing: 2.5px;
    color: #ffffff;
}

QLabel#brandTagline {
    font-size: 9px;
    color: #71717a;
    font-weight: 700;
    letter-spacing: 2px;
}

QPushButton#navButton {
    background-color: transparent;
    color: #a1a1aa;
    border: none;
    border-radius: 10px;
    padding: 9px 14px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
    text-align: left;
    min-height: 36px;
}

QPushButton#navButton:hover {
    background-color: rgba(255, 255, 255, 0.06);
    color: #ffffff;
}

QPushButton#navButton[active="true"] {
    background-color: rgba(255, 255, 255, 0.12);
    color: #ffffff;
    border-left: 3px solid #ffffff;
    font-weight: 800;
}

QLabel#navSectionLabel {
    font-size: 9px;
    font-weight: 800;
    color: #52525b;
    letter-spacing: 2px;
    padding: 4px 16px;
}

/* ── STATS CARD ── */
QFrame#statsCard {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
}

QLabel#statNumber {
    font-size: 24px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: -0.5px;
}

QLabel#statLabel {
    font-size: 9px;
    font-weight: 700;
    color: #71717a;
    letter-spacing: 1.5px;
}

/* ── BUTTONS (STRICT MONOCHROME) ── */
QPushButton#primaryButton {
    background-color: #ffffff;
    color: #000000;
    border: none;
    border-radius: 980px;
    padding: 10px 24px;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 1.5px;
    min-height: 38px;
}

QPushButton#primaryButton:hover {
    background-color: #e4e4e7;
}

QPushButton#primaryButton:pressed {
    background-color: #d4d4d8;
}

QPushButton#secondaryButton {
    background-color: rgba(255, 255, 255, 0.05);
    color: #e4e4e7;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 980px;
    padding: 9px 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    min-height: 36px;
}

QPushButton#secondaryButton:hover {
    background-color: rgba(255, 255, 255, 0.10);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: #ffffff;
}

QPushButton#dangerButton {
    background-color: rgba(255, 255, 255, 0.04);
    color: #a1a1aa;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 980px;
    padding: 7px 18px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    min-height: 32px;
}

QPushButton#dangerButton:hover {
    background-color: rgba(255, 255, 255, 0.12);
    color: #ffffff;
    border: 1px solid #ffffff;
}

QPushButton#iconTextButton {
    background-color: transparent;
    color: #a1a1aa;
    border: none;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 700;
    border-radius: 980px;
}

QPushButton#iconTextButton:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}

/* ── FILTER PILLS ── */
QPushButton#filterPill {
    background-color: rgba(255, 255, 255, 0.04);
    color: #a1a1aa;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 980px;
    padding: 6px 16px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    min-height: 30px;
}

QPushButton#filterPill:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.2);
}

QPushButton#filterPill[selected="true"] {
    background-color: rgba(255, 255, 255, 0.18);
    color: #ffffff;
    border: 1px solid #ffffff;
    font-weight: 800;
}

/* ── RESULT CARDS ── */
QFrame#resultCard {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 18px;
}

QFrame#resultCard:hover {
    background-color: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.35);
}

QLabel#resultTitle {
    font-size: 14px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#resultSnippet {
    font-size: 12px;
    color: #a1a1aa;
    line-height: 1.5;
}

QLabel#resultPath {
    font-size: 11px;
    color: #52525b;
}

QLabel#badgeLabel {
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    background-color: rgba(255, 255, 255, 0.06);
    color: #e4e4e7;
}

QLabel#rankScoreBadge {
    background-color: rgba(255, 255, 255, 0.10);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 700;
}

/* ── PREVIEW DRAWER ── */
QFrame#previewDrawer {
    background-color: rgba(14, 14, 18, 0.97);
    border-left: 1px solid rgba(255, 255, 255, 0.08);
}

QLabel#previewTitle {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
}

QTextEdit#previewText {
    background-color: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    color: #a1a1aa;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
    padding: 12px;
    selection-background-color: #3f3f46;
}

QFrame#previewMetaRow {
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
}

QLabel#previewMetaKey {
    font-size: 9px;
    font-weight: 800;
    color: #71717a;
    letter-spacing: 1.5px;
}

QLabel#previewMetaVal {
    font-size: 12px;
    font-weight: 500;
    color: #e4e4e7;
}

/* ── FOLDER CARDS ── */
QFrame#folderCard {
    background-color: #1e1e20;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 16px;
}

QFrame#folderCard:hover {
    background-color: #242428;
    border: 1px solid rgba(255, 255, 255, 0.25);
}

QLabel#folderName {
    font-size: 14px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#folderStats {
    font-size: 10px;
    font-weight: 600;
    color: #71717a;
    letter-spacing: 1.5px;
}

/* ── DROP ZONE ── */
QFrame#dropZone {
    background-color: #1e1e20;
    border: 1.5px dashed rgba(255, 255, 255, 0.20);
    border-radius: 18px;
    min-height: 120px;
}

QFrame#dropZone:hover {
    border: 1.5px dashed #ffffff;
    background-color: #242428;
}

QLabel#dropTitle {
    font-size: 14px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#dropSubtitle {
    font-size: 11px;
    font-weight: 400;
    color: #71717a;
    letter-spacing: 1px;
}

/* ── SECTION LABELS ── */
QLabel#sectionTitle {
    font-family: 'Friday', -apple-system, sans-serif;
    font-size: 26px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: 1px;
}

QLabel#sectionBadge {
    font-size: 10px;
    font-weight: 700;
    color: #a1a1aa;
    letter-spacing: 2px;
}

QLabel#mutedText {
    font-size: 10px;
    color: #71717a;
    letter-spacing: 1.5px;
    font-weight: 600;
}

/* ── DIAGNOSTICS / METRICS ── */
QFrame#metricCard {
    background-color: #1e1e20;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 16px;
}

QLabel#metricValue {
    font-size: 28px;
    font-weight: 900;
    color: #ffffff;
}

QLabel#metricLabel {
    font-size: 8px;
    font-weight: 800;
    color: #71717a;
    letter-spacing: 2px;
}

/* ── STATUS BAR ── */
QFrame#statusBar {
    background-color: rgba(10, 10, 14, 0.95);
    border-top: 1px solid rgba(255, 255, 255, 0.06);
}

QLabel#statusText {
    font-size: 10px;
    color: #71717a;
    letter-spacing: 1px;
    font-weight: 600;
}

QLabel#statusDot {
    color: #ffffff;
}

QProgressBar {
    background-color: rgba(255, 255, 255, 0.06);
    border: none;
    border-radius: 4px;
    max-height: 3px;
}

QProgressBar::chunk {
    background-color: #ffffff;
    border-radius: 4px;
}

/* ── SCROLL BARS ── */
QScrollBar:vertical {
    background-color: transparent;
    width: 5px;
    margin: 0px;
}

QScrollBar:handle:vertical {
    background-color: rgba(255, 255, 255, 0.12);
    min-height: 24px;
    border-radius: 3px;
}

QScrollBar:handle:vertical:hover {
    background-color: rgba(255, 255, 255, 0.35);
}

QScrollBar:add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    height: 0px;
}
"""

LIGHT_STYLESHEET = DARK_STYLESHEET
MAIN_STYLESHEET = DARK_STYLESHEET
