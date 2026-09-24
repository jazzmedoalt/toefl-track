"""Navigation rail with a sliding active-item pill."""
from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from .. import theme as T
from .cards import label


class _NavButton(QPushButton):
    def __init__(self, text, icon_name, parent=None):
        super().__init__("  " + text, parent)  # breathing room between icon and dot text
        self.icon_name = icon_name
        self.setCheckable(True)
        self.setFocusPolicy(Qt.TabFocus)  # keyboard focus ring only, not after mouse clicks
        self.setCursor(Qt.PointingHandCursor)
        self.setIconSize(QSize(18, 18))
        self.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid transparent; border-radius: 18px;"
            f" text-align: left; padding: 0 12px; min-height: 36px; max-height: 36px; color: {T.MUTED};"
            f" font-family: \"{T.DOT}\"; font-size: 16px; font-weight: 900; }}"
            f"QPushButton:hover {{ color: {T.TEXT}; background: rgba(255,255,255,0.03); }}"
            f"QPushButton:checked {{ color: {T.TEXT}; background: transparent; }}"
            f"QPushButton[kbd=\"true\"]:focus {{ border-color: {T.RED}; }}")
        self.refresh_icon()
        self.toggled.connect(lambda _: self.refresh_icon())

    def focusInEvent(self, e):
        # show the ring only for keyboard focus, not when focus arrives programmatically
        self.setProperty("kbd", e.reason() in (Qt.TabFocusReason, Qt.BacktabFocusReason))
        self.style().polish(self)
        super().focusInEvent(e)

    def refresh_icon(self):
        self.setIcon(T.icon(self.icon_name, T.TEXT if self.isChecked() else T.MUTED, 18))


class Sidebar(QWidget):
    navigate = Signal(int)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setFixedWidth(204)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 14)
        lay.setSpacing(4)
        lay.addWidget(label("MENU", "eyebrow"))
        lay.addSpacing(4)
        self.buttons = []
        for i, (text, icon_name) in enumerate(items):
            b = _NavButton(text, icon_name)
            b.clicked.connect(lambda _=False, i=i: self.select(i, emit=True))
            lay.addWidget(b)
            self.buttons.append(b)
        lay.addStretch(1)
        foot = label("● SAVED LOCALLY", "eyebrow")
        foot.setToolTip("Everything is saved automatically on this computer")
        lay.addWidget(foot)

        self._pill = QRectF()
        self._current = 0
        self._a = QVariantAnimation(self)
        self._a.setEasingCurve(QEasingCurve.OutCubic)
        self._a.valueChanged.connect(self._set_pill)
        self.buttons[0].setChecked(True)

    def _set_pill(self, r):
        self._pill = QRectF(r)
        self.update()

    def select(self, i, emit=False):
        for j, b in enumerate(self.buttons):
            b.setChecked(j == i)
        target = QRectF(self.buttons[i].geometry())
        if self._pill.isNull() or not self.isVisible():
            self._set_pill(target)
        else:
            self._a.stop()
            self._a.setDuration(T.dur(260))
            self._a.setStartValue(self._pill)
            self._a.setEndValue(target)
            self._a.start()
        self._current = i
        if emit:
            self.navigate.emit(i)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._set_pill(QRectF(self.buttons[self._current].geometry()))

    def showEvent(self, e):
        super().showEvent(e)
        self._set_pill(QRectF(self.buttons[self._current].geometry()))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self._pill.isNull():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T.RAISED))
            p.drawRoundedRect(self._pill, self._pill.height() / 2, self._pill.height() / 2)
            p.setBrush(QColor(T.RED))
            p.drawEllipse(QPointF(self._pill.right() - 16, self._pill.center().y()), 3.5, 3.5)
