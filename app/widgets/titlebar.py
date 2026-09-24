"""Custom title bar for the frameless window: logo, tour and theme buttons, window controls."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from .. import theme as T
from ..paths import resource
from .cards import label


class _WinButton(QPushButton):
    def __init__(self, icon_name, danger=False, tip="", parent=None):
        super().__init__(parent)
        self._icon = icon_name
        self._danger = danger
        self.setToolTip(tip)
        self.setAccessibleName(tip)
        self.setFixedSize(46, 36)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 0; min-height: 36px; padding: 0; }"
            + (f"QPushButton:hover {{ background: {T.RED}; }}" if danger
               else f"QPushButton:hover {{ background: {T.HOVER}; }}"))
        self.setIconSize(QSize(14, 14))
        self.setIcon(T.icon(icon_name, T.MUTED, 14))

    def enterEvent(self, e):
        self.setIcon(T.icon(self._icon, "#FFFFFF" if self._danger else T.TEXT, 14))
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.setIcon(T.icon(self._icon, T.MUTED, 14))
        super().leaveEvent(e)


class TitleBar(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self._win = window
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(QPixmap(resource("assets/icon.png")).scaled(
            40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setFixedSize(20, 20)
        logo.setScaledContents(True)
        lay.addWidget(logo)
        lay.addWidget(label("TOEFL TRACK", "eyebrow"))
        lay.addStretch(1)
        self.btn_help = _WinButton("circle-help", tip="Take the tour")
        self.btn_theme = _WinButton("sun" if T.MODE == "dark" else "moon",
                                    tip="Light mode" if T.MODE == "dark" else "Dark mode")
        for b in (self.btn_help, self.btn_theme):
            b.setFocusPolicy(Qt.TabFocus)
            lay.addWidget(b)
        self.btn_help.clicked.connect(window.start_tour)
        self.btn_theme.clicked.connect(
            lambda: window.toggle_theme(self.btn_theme.mapTo(window, self.btn_theme.rect().center())))
        self.btn_min = _WinButton("minus", tip="Minimize")
        self.btn_max = _WinButton("square", tip="Maximize")
        self.btn_close = _WinButton("x", danger=True, tip="Close")
        for b in (self.btn_min, self.btn_max, self.btn_close):
            lay.addWidget(b)
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(self.toggle_max)
        self.btn_close.clicked.connect(window.close)

    def toggle_max(self):
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._win.windowHandle():
            self._win.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.toggle_max()
