"""TOEFL Track: entry point and frameless main window."""
import sys

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter, QPalette,
                           QPen)
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from . import db
from . import theme as T
from .pages.dashboard import DashboardPage
from .pages.mistakes import MistakesPage
from .pages.sets import SetsPage
from .pages.settings import SettingsPage
from .paths import resource
from .widgets.sidebar import Sidebar
from .widgets.titlebar import TitleBar
from .widgets.toast import AnimatedStack, Toast

GRIP = 6  # px of window edge used for resizing
DASH, SETS, MISTAKES, SETTINGS = range(4)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("TOEFL Track")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        self.setMinimumSize(920, 620)
        self.resize(1160, 740)

        root = QVBoxLayout(self)
        self._root = root
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)
        self.titlebar = TitleBar(self)
        root.addWidget(self.titlebar)

        row = QHBoxLayout()
        row.setSpacing(0)
        self.sidebar = Sidebar([("Dashboard", "layout-dashboard"), ("Sets", "layers"),
                                ("Mistakes", "book-x"), ("Settings", "settings")])
        self.sidebar.navigate.connect(self.go)
        row.addWidget(self.sidebar)
        self.pages = AnimatedStack()
        self.dashboard = DashboardPage(self)
        self.sets = SetsPage(self)
        self.mistakes = MistakesPage(self)
        self.settings = SettingsPage(self)
        for p in (self.dashboard, self.sets, self.mistakes, self.settings):
            self.pages.addWidget(p)
        row.addWidget(self.pages, 1)
        root.addLayout(row, 1)

        self._toast = Toast(self)
        self.dashboard.refresh()

    # ---- navigation
    def go(self, index, direction=None):
        cur = self.pages.currentIndex()
        if cur == SETS and index == SETS:
            self.sets.show_list()  # re-clicking the nav item returns to its root
            return
        if cur == SETS:
            self.sets.editor.flush()
        self.pages.widget(index).refresh()
        self.pages.slide_to(index, direction or (1 if index > cur else -1))

    def go_sets(self, focus_new=False):
        self.sidebar.select(SETS)
        self.go(SETS)
        if focus_new:
            self.sets.focus_new()

    def open_practice(self, pid):
        self.sidebar.select(SETS)
        self.pages.slide_to(SETS, 1)
        self.sets.open_practice(pid)

    def toast(self, text, ms=1600):
        self._toast.show_message(text, ms)

    # ---- frameless resize
    def _edges(self, pos: QPoint):
        if self.isMaximized():
            return Qt.Edges()
        r = self.rect()
        e = Qt.Edges()
        if pos.x() <= GRIP:
            e |= Qt.LeftEdge
        if pos.x() >= r.width() - GRIP:
            e |= Qt.RightEdge
        if pos.y() <= GRIP:
            e |= Qt.TopEdge
        if pos.y() >= r.height() - GRIP:
            e |= Qt.BottomEdge
        return e

    def mouseMoveEvent(self, e):
        edges = self._edges(e.position().toPoint())
        cursors = {
            Qt.LeftEdge | Qt.TopEdge: Qt.SizeFDiagCursor, Qt.RightEdge | Qt.BottomEdge: Qt.SizeFDiagCursor,
            Qt.RightEdge | Qt.TopEdge: Qt.SizeBDiagCursor, Qt.LeftEdge | Qt.BottomEdge: Qt.SizeBDiagCursor,
            Qt.LeftEdge: Qt.SizeHorCursor, Qt.RightEdge: Qt.SizeHorCursor,
            Qt.TopEdge: Qt.SizeVerCursor, Qt.BottomEdge: Qt.SizeVerCursor,
        }
        self.setCursor(cursors.get(edges, Qt.ArrowCursor))
        super().mouseMoveEvent(e)

    def mousePressEvent(self, e):
        edges = self._edges(e.position().toPoint())
        if e.button() == Qt.LeftButton and edges and self.windowHandle():
            self.windowHandle().startSystemResize(edges)
            return
        super().mousePressEvent(e)

    def changeEvent(self, e):
        if e.type() == e.Type.WindowStateChange:
            m = 0 if self.isMaximized() else GRIP
            self._root.setContentsMargins(m, m, m, m)
            self.titlebar.btn_max.setToolTip("Restore" if self.isMaximized() else "Maximize")
        super().changeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        if not self.isMaximized():
            self._root.setContentsMargins(GRIP, GRIP, GRIP, GRIP)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(T.BG))
        if not self.isMaximized():
            p.setPen(QPen(QColor(T.BORDER), 1))
            p.drawRect(QRect(0, 0, self.width() - 1, self.height() - 1))


def _dark_palette() -> QPalette:
    """Force dark roles so nothing falls back to the OS light theme."""
    pal = QPalette()
    roles = {
        QPalette.Window: T.BG, QPalette.WindowText: T.TEXT, QPalette.Base: T.RAISED,
        QPalette.AlternateBase: T.SURFACE, QPalette.Text: T.TEXT, QPalette.Button: T.RAISED,
        QPalette.ButtonText: T.TEXT, QPalette.Highlight: T.ACCENT_BTN, QPalette.HighlightedText: "#FFFFFF",
        QPalette.ToolTipBase: T.RAISED, QPalette.ToolTipText: T.TEXT, QPalette.PlaceholderText: T.FAINT,
        QPalette.Link: T.ACCENT, QPalette.Mid: T.BORDER, QPalette.Dark: T.BG, QPalette.Light: T.HOVER,
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, QColor(T.FAINT))
    return pal


def create_app() -> QApplication:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("TOEFL Track")
    app.setStyle("Fusion")  # consistent base on every OS; our QSS sits on top
    app.setPalette(_dark_palette())
    for w in ("Regular", "Medium", "SemiBold", "Bold"):
        QFontDatabase.addApplicationFont(resource(f"assets/fonts/Inter-{w}.ttf"))
    font = QFont(T.FONT)
    font.setPixelSize(14)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)
    app.setStyleSheet(T.QSS)
    app.setWindowIcon(QIcon(resource("assets/icon.png")))
    T.MOTION["enabled"] = db.get_setting("reduce_motion", "0") != "1"
    return app


def main():
    app = create_app()
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
