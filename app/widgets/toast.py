"""Transient notification that fades in at the bottom of the window, and a page stack that
fades and slides between pages."""
from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, Qt,
                            QTimer)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QStackedWidget

from .. import theme as T


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"background: {T.RAISED}; border: 1px solid {T.BORDER_HI}; border-radius: 10px;"
            f" padding: 8px 16px; color: {T.TEXT}; font-weight: 500;")
        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0)
        self.setGraphicsEffect(self._fx)
        self._fade = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade.finished.connect(self._on_faded)
        self._timer = QTimer(self, singleShot=True, timeout=self._hide)
        self.hide()

    def show_message(self, text, ms=1600):
        self.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        self.move((par.width() - self.width()) // 2, par.height() - self.height() - 28)
        self.show()
        self.raise_()
        self._fade.stop()
        self._fade.setDuration(T.dur(160))
        self._fade.setEasingCurve(T.EASE_IN)
        self._fade.setStartValue(self._fx.opacity())
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start(ms)

    def _hide(self):
        self._fade.stop()
        self._fade.setDuration(T.dur(220))
        self._fade.setEasingCurve(T.EASE_OUT)
        self._fade.setStartValue(self._fx.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _on_faded(self):
        if self._fx.opacity() == 0:
            self.hide()


class AnimatedStack(QStackedWidget):
    """Switches pages with a short fade + slide (forward slides left, back slides right)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._group = self._widget = None

    def slide_to(self, index, direction=1):
        if index == self.currentIndex():
            return
        self.setCurrentIndex(index)
        if not T.MOTION["enabled"]:
            return
        w = self.currentWidget()
        fx = QGraphicsOpacityEffect(w)
        fx.setOpacity(0)
        w.setGraphicsEffect(fx)
        end = QPoint(0, 0)
        fade = QPropertyAnimation(fx, b"opacity")
        fade.setDuration(260)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        slide = QPropertyAnimation(w, b"pos")
        slide.setDuration(300)
        slide.setStartValue(QPoint(24 * direction, 0))
        slide.setEndValue(end)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        self._finish()
        g = QParallelAnimationGroup(self)
        g.addAnimation(fade)
        g.addAnimation(slide)
        g.finished.connect(self._finish)
        self._group, self._widget = g, w
        g.start()

    def _finish(self):
        if self._group is None:
            return
        g, w = self._group, self._widget
        self._group = self._widget = None
        g.stop()
        g.deleteLater()
        w.setGraphicsEffect(None)   # tables/text render crisper without the effect
        w.move(0, 0)
