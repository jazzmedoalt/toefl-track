"""Nothing OS–inspired design tokens: AMOLED black, white, one red; dot-matrix type and dots.
Also the QSS stylesheet, icon loader, font helpers and motion settings."""
from functools import lru_cache

from PySide6.QtCore import QByteArray, QEasingCurve, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .paths import resource

# ---- color tokens (role-based) ----
BG = "#000000"          # AMOLED black
SURFACE = "#0B0B0B"     # cards
RAISED = "#141414"      # inputs, hovered rows
HOVER = "#1C1C1C"
BORDER = "#222222"      # hairlines
BORDER_HI = "#3A3A3A"
TEXT = "#FFFFFF"
MUTED = "#9A9A9A"       # ~7:1 on black
FAINT = "#4A4A4A"       # dots, gridlines, placeholders only
RED = "#D71921"         # the one accent: indicators, big numbers, dots
RED_TEXT = "#FF4D4D"    # red for small text (passes 4.5:1 on black)
ACCENT = RED
DANGER = RED_TEXT
MID = "#8C8C8C"         # middle scores
GOOD = TEXT             # high scores are plain white

FONT = "Space Grotesk"  # body
DOT = "Doto"            # dot-matrix display
MONO = "Space Mono"     # system labels

# ---- motion ----
MOTION = {"enabled": True}
EASE_IN = QEasingCurve.OutCubic      # entering: decelerate
EASE_OUT = QEasingCurve.InCubic      # leaving: accelerate


def dur(ms: int) -> int:
    """Duration honoring the reduce-motion setting."""
    return ms if MOTION["enabled"] else 0


def score_color(score) -> str:
    """Red < 5, grey 5–7, white 8–10. Always shown next to the x/10 text."""
    if score is None:
        return FAINT
    if score >= 8:
        return GOOD
    if score >= 5:
        return MID
    return RED_TEXT


def score_label(score) -> str:
    if score is None:
        return "No score"
    if score >= 8:
        return "Strong"
    if score >= 5:
        return "Okay"
    return "Needs work"


def mix(c1: str, c2: str, t: float) -> QColor:
    a, b = QColor(c1), QColor(c2)
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


def font(px: int, weight=QFont.Normal, family: str = FONT) -> QFont:
    f = QFont(family)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def dot_font(px: int) -> QFont:
    return font(px, QFont.Black, DOT)


def mono_font(px: int, spacing: float = 1.0) -> QFont:
    f = font(px, QFont.Normal, MONO)
    f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def dot_row(p: QPainter, rect: QRectF, fraction: float, on=TEXT, off=FAINT, pitch: float = 7.0):
    """A segmented row of dots filled left to right (Nothing-style progress)."""
    r = min(rect.height(), pitch) / 2 - 0.5
    n = max(1, int(rect.width() // pitch))
    lit = round(n * max(0.0, min(1.0, fraction)))
    p.setPen(Qt.NoPen)
    for i in range(n):
        p.setBrush(QColor(on if i < lit else off))
        p.drawEllipse(QPointF(rect.left() + pitch * i + pitch / 2, rect.center().y()), r, r)


def dotted_hline(p: QPainter, x1: float, x2: float, y: float, color=FAINT, pitch: float = 6.0, r: float = 0.9):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    x = x1
    while x <= x2:
        p.drawEllipse(QPointF(x, y), r, r)
        x += pitch


@lru_cache(maxsize=256)
def icon_pixmap(name: str, color: str = MUTED, size: int = 18, dpr: float = 2.0) -> QPixmap:
    with open(resource(f"assets/icons/{name}.svg"), encoding="utf-8") as f:
        # thinner strokes read closer to Nothing's glyph icons
        svg = f.read().replace("currentColor", color).replace('stroke-width="2"', 'stroke-width="1.6"')
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str = MUTED, size: int = 18) -> QIcon:
    return QIcon(icon_pixmap(name, color, size))


CHEVRON = resource("assets/icons/chevron-down-muted.svg").replace("\\", "/")

QSS = f"""
* {{
    font-family: "{FONT}";
    color: {TEXT};
    outline: none;
}}
QWidget#Root {{ background: {BG}; }}
QToolTip {{
    background: {RAISED}; color: {TEXT}; border: 1px solid {BORDER_HI};
    border-radius: 8px; padding: 5px 8px; font-family: "{MONO}"; font-size: 12px;
}}
QLabel {{ background: transparent; }}
QLabel[role="h1"] {{ font-family: "{DOT}"; font-size: 32px; font-weight: 900; }}
QLabel[role="h2"] {{ font-family: "{DOT}"; font-size: 20px; font-weight: 900; }}
QLabel[role="display"] {{ font-family: "{DOT}"; font-size: 46px; font-weight: 900; }}
QLabel[role="display-sm"] {{ font-family: "{DOT}"; font-size: 26px; font-weight: 900; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="caption"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="eyebrow"] {{
    color: {MUTED}; font-family: "{MONO}"; font-size: 11px; letter-spacing: 1.5px;
}}

/* ---- buttons: pills ---- */
QPushButton {{
    background: transparent; border: 1px solid {BORDER_HI}; border-radius: 17px;
    padding: 7px 16px; font-weight: 500; min-height: 18px;
}}
QPushButton:hover {{ background: {HOVER}; border-color: {MUTED}; }}
QPushButton:pressed {{ background: {RAISED}; }}
QPushButton:focus {{ border-color: {TEXT}; }}
QPushButton:disabled {{ color: {FAINT}; border-color: {BORDER}; }}
QPushButton[kind="primary"] {{ background: {TEXT}; border: 1px solid {TEXT}; color: #000000; font-weight: 600; }}
QPushButton[kind="primary"]:hover {{ background: #E6E6E6; }}
QPushButton[kind="primary"]:focus {{ border: 2px solid {RED}; }}
QPushButton[kind="primary"]:disabled {{ background: {RAISED}; border-color: {BORDER}; color: {FAINT}; }}
QPushButton[kind="ghost"] {{ border-color: transparent; color: {MUTED}; }}
QPushButton[kind="ghost"]:hover {{ background: {RAISED}; color: {TEXT}; }}
QPushButton[kind="danger"] {{ border-color: transparent; color: {RED_TEXT}; }}
QPushButton[kind="danger"]:hover {{ background: rgba(215,25,33,0.14); }}
QPushButton[kind="icon"] {{
    border: none; border-radius: 8px; padding: 4px; min-height: 0;
}}
QPushButton[kind="icon"]:hover {{ background: {HOVER}; }}

/* ---- inputs ---- */
QLineEdit, QPlainTextEdit, QDateEdit, QComboBox {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
    padding: 7px 12px; selection-background-color: {RED}; selection-color: {TEXT};
}}
QLineEdit:hover, QPlainTextEdit:hover, QDateEdit:hover, QComboBox:hover {{ border-color: {BORDER_HI}; }}
QLineEdit:focus, QPlainTextEdit:focus, QDateEdit:focus, QComboBox:focus {{ border-color: {TEXT}; }}
QLineEdit[role="title"] {{
    background: transparent; border: 1px solid transparent; font-family: "{DOT}"; font-size: 30px;
    font-weight: 900; padding: 0 6px; margin-left: -6px;
}}
QLineEdit[role="title"]:hover {{ border-color: {BORDER}; }}
QLineEdit[role="title"]:focus {{ border-color: {TEXT}; background: {SURFACE}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url("{CHEVRON}"); width: 14px; height: 14px; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {RAISED}; border: 1px solid {BORDER_HI}; border-radius: 10px; padding: 4px;
    selection-background-color: {HOVER}; selection-color: {TEXT};
}}
QCalendarWidget QWidget {{ alternate-background-color: {RAISED}; background: {SURFACE}; }}
QCalendarWidget QToolButton {{ background: transparent; border: none; padding: 4px 8px; font-weight: 600; }}
QCalendarWidget QToolButton:hover {{ background: {HOVER}; border-radius: 6px; }}
QCalendarWidget QAbstractItemView:enabled {{
    background: {SURFACE}; selection-background-color: {RED}; selection-color: {TEXT};
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {FAINT}; }}
QCalendarWidget QMenu {{ background: {RAISED}; }}
QCalendarWidget QSpinBox {{ background: {RAISED}; border: none; }}

/* ---- tables ---- */
QTableWidget {{
    background: transparent; border: none; gridline-color: transparent;
    selection-background-color: {HOVER}; selection-color: {TEXT};
}}
QTableWidget::item {{ padding: 0 10px; border-bottom: 1px dotted {BORDER_HI}; }}
QTableWidget::item:hover {{ background: {RAISED}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 8px 10px; font-family: "{MONO}"; font-size: 11px; letter-spacing: 1px;
}}
QTableWidget QLineEdit {{ border-radius: 6px; padding: 2px 6px; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* ---- scrollbars ---- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_HI}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_HI}; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; border: none; width: 0; height: 0;
}}

QMenu {{ background: {RAISED}; border: 1px solid {BORDER_HI}; border-radius: 10px; padding: 4px; }}
QMenu::item {{ padding: 6px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {HOVER}; }}
QMenu::item:disabled {{ color: {FAINT}; }}
QCheckBox {{ spacing: 8px; color: {MUTED}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 8px; border: 1px solid {BORDER_HI}; background: {SURFACE};
}}
QCheckBox::indicator:checked {{ background: {RED}; border-color: {RED}; }}
"""
