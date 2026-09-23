"""Design tokens, QSS stylesheet, icon loader and motion settings (dark only)."""
from functools import lru_cache

from PySide6.QtCore import QByteArray, QEasingCurve, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .paths import resource

# ---- color tokens (role-based) ----
BG = "#0B0D12"          # window background
SURFACE = "#12151C"     # cards
RAISED = "#181C25"      # inputs, hovered rows
HOVER = "#1F2430"
BORDER = "#242936"
BORDER_HI = "#343B4C"
TEXT = "#E7E9EE"
MUTED = "#97A0B3"       # ~7:1 on SURFACE
FAINT = "#5D6577"       # gridlines / placeholders only
ACCENT = "#8B7CFF"      # violet (lines, focus, highlights)
ACCENT_BTN = "#6E5BF7"  # button fill (white text passes 4.5:1)
ACCENT_2 = "#3DD6F5"    # cyan (gradient end)
DANGER = "#F87171"
WARN = "#FBBF24"
GOOD = "#34D399"

FONT = "Inter"

# ---- motion ----
MOTION = {"enabled": True}
EASE_IN = QEasingCurve.OutCubic      # entering: decelerate
EASE_OUT = QEasingCurve.InCubic      # leaving: accelerate


def dur(ms: int) -> int:
    """Duration honoring the reduce-motion setting."""
    return ms if MOTION["enabled"] else 0


def score_color(score) -> str:
    if score is None:
        return FAINT
    if score >= 8:
        return GOOD
    if score >= 5:
        return WARN
    return DANGER


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


@lru_cache(maxsize=256)
def icon_pixmap(name: str, color: str = MUTED, size: int = 18, dpr: float = 2.0) -> QPixmap:
    with open(resource(f"assets/icons/{name}.svg"), encoding="utf-8") as f:
        svg = f.read().replace("currentColor", color)
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
    border-radius: 6px; padding: 5px 8px;
}}
QLabel {{ background: transparent; }}
QLabel[role="h1"] {{ font-size: 22px; font-weight: 600; }}
QLabel[role="h2"] {{ font-size: 15px; font-weight: 600; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="caption"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="eyebrow"] {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}

/* ---- buttons ---- */
QPushButton {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 7px 14px; font-weight: 500; min-height: 20px;
}}
QPushButton:hover {{ background: {HOVER}; border-color: {BORDER_HI}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:focus {{ border-color: {ACCENT}; }}
QPushButton[kind="primary"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_BTN}, stop:1 #5A48E8);
    border: 1px solid #7B6AFF; color: white;
}}
QPushButton[kind="primary"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C6BFF, stop:1 #6553F0);
}}
QPushButton[kind="primary"]:focus {{ border-color: {ACCENT_2}; }}
QPushButton[kind="ghost"] {{ background: transparent; border-color: transparent; color: {MUTED}; }}
QPushButton[kind="ghost"]:hover {{ background: {RAISED}; color: {TEXT}; }}
QPushButton[kind="danger"] {{ background: transparent; border-color: transparent; color: {DANGER}; }}
QPushButton[kind="danger"]:hover {{ background: rgba(248,113,113,0.12); }}
QPushButton[kind="icon"] {{
    background: transparent; border: none; border-radius: 6px; padding: 4px; min-height: 0;
}}
QPushButton[kind="icon"]:hover {{ background: {HOVER}; }}

/* ---- inputs ---- */
QLineEdit, QPlainTextEdit, QDateEdit, QComboBox {{
    background: {RAISED}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 7px 10px; selection-background-color: {ACCENT_BTN};
}}
QLineEdit:hover, QPlainTextEdit:hover, QDateEdit:hover, QComboBox:hover {{ border-color: {BORDER_HI}; }}
QLineEdit:focus, QPlainTextEdit:focus, QDateEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QLineEdit[role="title"] {{
    background: transparent; border: 1px solid transparent; font-size: 22px; font-weight: 600;
    padding: 2px 6px; margin-left: -6px;
}}
QLineEdit[role="title"]:hover {{ border-color: {BORDER}; }}
QLineEdit[role="title"]:focus {{ border-color: {ACCENT}; background: {RAISED}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url("{CHEVRON}"); width: 14px; height: 14px; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {RAISED}; border: 1px solid {BORDER_HI}; border-radius: 8px; padding: 4px;
    selection-background-color: {HOVER}; selection-color: {TEXT};
}}
QCalendarWidget QWidget {{ alternate-background-color: {RAISED}; background: {SURFACE}; }}
QCalendarWidget QToolButton {{ background: transparent; border: none; padding: 4px 8px; font-weight: 600; }}
QCalendarWidget QToolButton:hover {{ background: {HOVER}; border-radius: 6px; }}
QCalendarWidget QAbstractItemView:enabled {{
    background: {SURFACE}; selection-background-color: {ACCENT_BTN}; selection-color: white;
}}
QCalendarWidget QAbstractItemView:disabled {{ color: {FAINT}; }}
QCalendarWidget QMenu {{ background: {RAISED}; }}
QCalendarWidget QSpinBox {{ background: {RAISED}; border: none; }}

/* ---- tables ---- */
QTableWidget {{
    background: transparent; border: none; gridline-color: transparent;
    selection-background-color: {HOVER}; selection-color: {TEXT};
    alternate-background-color: rgba(255,255,255,0.015);
}}
QTableWidget::item {{ padding: 0 10px; border-bottom: 1px solid {BORDER}; }}
QTableWidget::item:hover {{ background: {RAISED}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 8px 10px; font-size: 11px; font-weight: 600; text-transform: uppercase;
}}
QTableWidget QLineEdit {{ border-radius: 4px; padding: 2px 6px; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* ---- scrollbars ---- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_HI}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {FAINT}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_HI}; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; border: none; width: 0; height: 0;
}}

QMenu {{ background: {RAISED}; border: 1px solid {BORDER_HI}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 14px; border-radius: 5px; }}
QMenu::item:selected {{ background: {HOVER}; }}
QCheckBox {{ spacing: 8px; }}
"""
