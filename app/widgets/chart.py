"""Score-trend area chart painted with QPainter: animated draw-in and hover values."""
from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .. import theme as T

PAD_L, PAD_R, PAD_T, PAD_B = 30, 12, 12, 24


class TrendChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []   # [{score, name, set_name, date}]
        self._t = 1.0
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(190)
        self._a = QVariantAnimation(self)
        self._a.setEasingCurve(QEasingCurve.OutCubic)
        self._a.valueChanged.connect(self._set)

    def _set(self, v):
        self._t = float(v)
        self.update()

    def set_points(self, pts):
        self._points = pts[-30:]
        self._hover = -1
        self._a.stop()
        self._a.setDuration(T.dur(900))
        self._a.setStartValue(0.0)
        self._a.setEndValue(1.0)
        self._a.start()
        if not T.MOTION["enabled"]:
            self._set(1.0)

    # geometry
    def _plot(self):
        return QRectF(PAD_L, PAD_T, self.width() - PAD_L - PAD_R, self.height() - PAD_T - PAD_B)

    def _xy(self, i, score):
        r = self._plot()
        n = len(self._points)
        x = r.left() + (r.width() * i / (n - 1) if n > 1 else r.width() / 2)
        y = r.bottom() - r.height() * score / 10
        return QPointF(x, y)

    def mouseMoveEvent(self, e):
        if len(self._points) < 2:
            return
        x = e.position().x()
        best = min(range(len(self._points)), key=lambda i: abs(self._xy(i, 0).x() - x))
        if best != self._hover:
            self._hover = best
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self._plot()
        f = QFont(T.FONT)
        f.setPixelSize(11)
        p.setFont(f)

        # grid + y labels
        for v in (0, 5, 10):
            y = r.bottom() - r.height() * v / 10
            p.setPen(QPen(QColor(T.BORDER), 1, Qt.DashLine if v else Qt.SolidLine))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(QColor(T.FAINT))
            p.drawText(QRectF(0, y - 8, PAD_L - 8, 16), Qt.AlignRight | Qt.AlignVCenter, str(v))

        n = len(self._points)
        if n < 2:
            p.setPen(QColor(T.MUTED))
            f.setPixelSize(13)
            p.setFont(f)
            p.drawText(r, Qt.AlignCenter, "Score at least 2 practices to see your trend")
            return

        pts = [self._xy(i, d["score"]) for i, d in enumerate(self._points)]
        line = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):
            mx = (a.x() + b.x()) / 2
            line.cubicTo(QPointF(mx, a.y()), QPointF(mx, b.y()), b)

        # reveal left→right
        p.save()
        p.setClipRect(QRectF(0, 0, r.left() + (r.width() + 8) * self._t, self.height()))
        area = QPainterPath(line)
        area.lineTo(pts[-1].x(), r.bottom())
        area.lineTo(pts[0].x(), r.bottom())
        area.closeSubpath()
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        top = QColor(T.ACCENT)
        top.setAlphaF(0.30)
        bottom = QColor(T.ACCENT)
        bottom.setAlphaF(0.0)
        g.setColorAt(0, top)
        g.setColorAt(1, bottom)
        p.fillPath(area, g)
        lg = QLinearGradient(r.left(), 0, r.right(), 0)
        lg.setColorAt(0, QColor(T.ACCENT))
        lg.setColorAt(1, QColor(T.ACCENT_2))
        p.setPen(QPen(lg, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(line)
        for i, pt in enumerate(pts):
            p.setPen(QPen(QColor(T.SURFACE), 2))
            p.setBrush(QColor(T.score_color(self._points[i]["score"])))
            p.drawEllipse(pt, 4.5 if i == self._hover else 3.5, 4.5 if i == self._hover else 3.5)
        p.restore()

        # x labels: first / last
        p.setPen(QColor(T.FAINT))
        p.drawText(QRectF(r.left() - 20, r.bottom() + 6, 120, 16), Qt.AlignLeft, "first")
        p.drawText(QRectF(r.right() - 100, r.bottom() + 6, 100, 16), Qt.AlignRight, "latest")

        # hover tooltip
        if 0 <= self._hover < n:
            d = self._points[self._hover]
            pt = pts[self._hover]
            p.setPen(QPen(QColor(T.BORDER_HI), 1, Qt.DashLine))
            p.drawLine(QPointF(pt.x(), r.top()), QPointF(pt.x(), r.bottom()))
            title = f"{d['score']}/10"
            sub = f"{d['set_name']} · {d['name']}"
            f.setPixelSize(12)
            p.setFont(f)
            w = max(p.fontMetrics().horizontalAdvance(sub), 40) + 20
            box = QRectF(pt.x() + 10, pt.y() - 50, w, 42)
            if box.right() > self.width() - 4:
                box.moveRight(pt.x() - 10)
            if box.top() < 2:
                box.moveTop(pt.y() + 10)
            p.setPen(QPen(QColor(T.BORDER_HI), 1))
            p.setBrush(QColor(T.RAISED))
            p.drawRoundedRect(box, 8, 8)
            p.setPen(QColor(T.score_color(d["score"])))
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            p.drawText(box.adjusted(10, 5, -10, -20), Qt.AlignLeft | Qt.AlignVCenter, title)
            p.setPen(QColor(T.MUTED))
            f.setWeight(QFont.Normal)
            p.setFont(f)
            p.drawText(box.adjusted(10, 20, -10, -4), Qt.AlignLeft | Qt.AlignVCenter, sub)
