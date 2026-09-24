"""TOEFL Track: entry point and frameless main window."""
import math
import sys

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QRect, QRectF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QPainter, QPainterPath,
                           QPalette, QPen)
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget

from . import db
from . import theme as T
from .pages.breakpoints import BreakpointsPage
from .pages.calendar import CalendarPage
from .pages.dashboard import DashboardPage
from .pages.flashcards import FlashcardsPage
from .pages.mistakes import MistakesPage
from .pages.quiz import QuizPage
from .pages.sets import SetsPage
from .pages.settings import SettingsPage
from .paths import resource
from .widgets.sidebar import Sidebar
from .widgets.titlebar import TitleBar
from .widgets.toast import AnimatedStack, Toast

GRIP = 6  # px of window edge used for resizing
DASH, SETS, CALENDAR, MISTAKES, BREAKPOINTS, FLASHCARDS, QUIZ, SETTINGS = range(8)


class MainWindow(QWidget):
    DASH, SETS, CALENDAR, MISTAKES, BREAKPOINTS, FLASHCARDS, QUIZ, SETTINGS = (
        DASH, SETS, CALENDAR, MISTAKES, BREAKPOINTS, FLASHCARDS, QUIZ, SETTINGS)

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self.setWindowTitle("TOEFL Track")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        self.setMinimumSize(920, 620)
        self.resize(1160, 740)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(1, 1, 1, 1)
        self._root.setSpacing(0)
        self.shell = self._toast = self._tour = None
        self._tour_checked = False
        self._build()

    def _build(self):
        """Create everything inside the window. Called again after a theme switch."""
        self.shell = QWidget(self)
        root = QVBoxLayout(self.shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._root.addWidget(self.shell)
        self.titlebar = TitleBar(self)
        root.addWidget(self.titlebar)

        row = QHBoxLayout()
        row.setSpacing(0)
        self.sidebar = Sidebar([("Dashboard", "layout-dashboard"), ("Sets", "layers"), ("Calendar", "calendar-days"),
                                ("Mistakes", "book-x"), ("Breakpoints", "crosshair"), ("Flashcards", "sparkles"), ("Quiz", "brain"),
                                ("Settings", "settings")])
        self.sidebar.navigate.connect(self.go)
        row.addWidget(self.sidebar)
        self.pages = AnimatedStack()
        self.dashboard = DashboardPage(self)
        self.sets = SetsPage(self)
        self.calendar = CalendarPage(self)
        self.mistakes = MistakesPage(self)
        self.breakpoints = BreakpointsPage(self)
        self.flashcards = FlashcardsPage(self)
        self.quiz = QuizPage(self)
        self.settings = SettingsPage(self)
        for p in (self.dashboard, self.sets, self.calendar, self.mistakes, self.breakpoints, self.flashcards, self.quiz, self.settings):
            self.pages.addWidget(p)
        row.addWidget(self.pages, 1)
        root.addLayout(row, 1)

        self._toast = Toast(self)
        self.dashboard.refresh()

    # ---- theme
    def set_theme(self, mode, origin=None):
        if mode == T.MODE:
            return
        old = self.grab()
        cur = self.pages.currentIndex()
        pid = None
        if cur == SETS:
            self.sets.editor.flush()
            if self.sets.stack.currentWidget() is self.sets.editor:
                pid = self.sets.editor.pid
        if self._tour:
            self._tour.close_tour(mark_done=False)
        T.apply(mode)
        db.set_setting("theme", T.MODE)
        app = QApplication.instance()
        app.setPalette(_palette())
        app.setStyleSheet(T.qss())
        self.shell.hide()
        self.shell.deleteLater()
        self._toast.deleteLater()
        self._build()
        self.titlebar.btn_max.setToolTip("Restore" if self.isMaximized() else "Maximize")
        self.sidebar.select(cur)
        self.pages.setCurrentIndex(cur)
        self.pages.currentWidget().refresh()
        if pid is not None:
            self.sets.open_practice(pid)
        self.update()
        if T.MOTION["enabled"]:
            _Reveal(self, old, origin or QPoint(self.width() - 60, 18))

    def toggle_theme(self, origin=None):
        self.set_theme("light" if T.MODE == "dark" else "dark", origin)

    # ---- tour
    def start_tour(self):
        if self._tour:
            return
        from .widgets.tour import Tour
        self._tour = Tour(self)
        self._tour.closed.connect(self._tour_closed)
        self._tour.start()

    def _tour_closed(self):
        self._tour = None

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

    def go_page(self, index):
        self.sidebar.select(index)
        self.go(index)

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
        if not self._tour_checked:
            self._tour_checked = True
            if db.get_setting("tour_done", "0") != "1":
                QTimer.singleShot(700, self.start_tour)   # first launch: meet Dot

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(T.BG))
        # Nothing-style dot grid across the whole window
        dot = QColor(T.TEXT)
        dot.setAlphaF(T.GRID_ALPHA)
        p.setPen(Qt.NoPen)
        p.setBrush(dot)
        r = e.rect()
        step = 18
        for y in range(r.top() - r.top() % step + 9, r.bottom() + 1, step):
            for x in range(r.left() - r.left() % step + 9, r.right() + 1, step):
                p.drawEllipse(QPoint(x, y), 1, 1)
        if not self.isMaximized():
            p.setPen(QPen(QColor(T.BORDER), 1))
            p.setBrush(Qt.NoBrush)  # otherwise the dot brush floods the window grey
            p.drawRect(QRect(0, 0, self.width() - 1, self.height() - 1))


class _Reveal(QWidget):
    """Theme switch effect: the old look shrinks away outside a circle growing from `origin`."""

    def __init__(self, win, pixmap, origin):
        super().__init__(win)
        self._pm = pixmap
        self._o = QPointF(origin)
        self._r = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(win.rect())
        far = max(math.hypot(self._o.x() - x, self._o.y() - y) for x in (0, self.width()) for y in (0, self.height()))
        self._a = QVariantAnimation(self, startValue=0.0, endValue=far + 4, duration=450,
                                    easingCurve=QEasingCurve.OutCubic)
        self._a.valueChanged.connect(self._tick)
        self._a.finished.connect(self.deleteLater)
        self.show()
        self.raise_()
        self._a.start()

    def _tick(self, v):
        self._r = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        keep = QPainterPath()
        keep.addRect(QRectF(self.rect()))
        hole = QPainterPath()
        hole.addEllipse(self._o, self._r, self._r)
        p.setClipPath(keep.subtracted(hole))
        p.drawPixmap(0, 0, self._pm)
        # red dotted rim on the growing edge
        p.setClipping(False)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.RED))
        n = max(12, int(self._r / 6))
        for i in range(n):
            a = 2 * math.pi * i / n
            p.drawEllipse(QPointF(self._o.x() + self._r * math.cos(a), self._o.y() + self._r * math.sin(a)), 1.6, 1.6)


def _palette() -> QPalette:
    """Palette from the current tokens, so nothing falls back to the OS theme."""
    pal = QPalette()
    roles = {
        QPalette.Window: T.BG, QPalette.WindowText: T.TEXT, QPalette.Base: T.RAISED,
        QPalette.AlternateBase: T.SURFACE, QPalette.Text: T.TEXT, QPalette.Button: T.RAISED,
        QPalette.ButtonText: T.TEXT, QPalette.Highlight: T.RED, QPalette.HighlightedText: "#FFFFFF",
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
    app.setDesktopFileName("io.github.jazzmedoalt.toefltrack")  # matches the AppImage .desktop (icon on Wayland)
    app.setStyle("Fusion")  # consistent base on every OS; our QSS sits on top
    T.apply(db.get_setting("theme", "dark"))
    app.setPalette(_palette())
    for f in ("Doto.ttf", "SpaceGrotesk.ttf", "SpaceMono-Regular.ttf", "SpaceMono-Bold.ttf"):
        QFontDatabase.addApplicationFont(resource(f"assets/fonts/{f}"))
    font = QFont(T.FONT)
    font.setPixelSize(14)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)
    app.setStyleSheet(T.qss())
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
