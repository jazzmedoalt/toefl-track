"""QPainter charts in dots: score trend (a trail of dots) and a GitHub-style activity heatmap."""
from datetime import date, timedelta

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QToolTip, QWidget

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
        p.setFont(T.mono_font(10, 0))

        # dotted grid + y labels
        for v in (0, 5, 10):
            y = r.bottom() - r.height() * v / 10
            T.dotted_hline(p, r.left(), r.right(), y, T.BORDER_HI if v == 0 else T.FAINT, 7, 0.9)
            p.setPen(QColor(T.MUTED))
            p.drawText(QRectF(0, y - 8, PAD_L - 8, 16), Qt.AlignRight | Qt.AlignVCenter, str(v))

        n = len(self._points)
        if n < 2:
            p.setPen(QColor(T.MUTED))
            p.setFont(T.font(13))
            p.drawText(r, Qt.AlignCenter, "Score at least 2 practices to see your trend")
            return

        pts = [self._xy(i, d["score"]) for i, d in enumerate(self._points)]
        line = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):
            mx = (a.x() + b.x()) / 2
            line.cubicTo(QPointF(mx, a.y()), QPointF(mx, b.y()), b)

        # the line itself is drawn as a trail of dots, revealed left→right
        p.save()
        p.setClipRect(QRectF(0, 0, r.left() + (r.width() + 8) * self._t, self.height()))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.TEXT))
        length = line.length()
        steps = max(2, int(length / 6))
        for k in range(steps + 1):
            p.drawEllipse(line.pointAtPercent(line.percentAtLength(length * k / steps)), 1.4, 1.4)
        for i, pt in enumerate(pts):
            s = self._points[i]["score"]
            big = 5.5 if i == self._hover else 4.5
            p.setPen(QPen(QColor(T.BG), 2))
            p.setBrush(QColor(T.RED if s < 5 else T.TEXT))
            p.drawEllipse(pt, big, big)
        p.restore()

        # x labels: first / last
        p.setFont(T.mono_font(10, 1))
        p.setPen(QColor(T.MUTED))
        p.drawText(QRectF(r.left() - 20, r.bottom() + 6, 120, 16), Qt.AlignLeft, "FIRST")
        p.drawText(QRectF(r.right() - 100, r.bottom() + 6, 100, 16), Qt.AlignRight, "LATEST")

        # hover tooltip
        if 0 <= self._hover < n:
            d = self._points[self._hover]
            pt = pts[self._hover]
            p.setPen(QPen(QColor(T.BORDER_HI), 1, Qt.DotLine))
            p.drawLine(QPointF(pt.x(), r.top()), QPointF(pt.x(), r.bottom()))
            sub = f"{d['set_name']} · {d['name']}"
            p.setFont(T.font(12))
            w = max(p.fontMetrics().horizontalAdvance(sub), 60) + 24
            box = QRectF(pt.x() + 10, pt.y() - 56, w, 48)
            if box.right() > self.width() - 4:
                box.moveRight(pt.x() - 10)
            if box.top() < 2:
                box.moveTop(pt.y() + 10)
            p.setPen(QPen(QColor(T.BORDER_HI), 1))
            p.setBrush(QColor(T.RAISED))
            p.drawRoundedRect(box, 10, 10)
            p.setPen(QColor(T.score_color(d["score"])))
            p.setFont(T.dot_font(20))
            p.drawText(box.adjusted(12, 4, -12, -22), Qt.AlignLeft | Qt.AlignVCenter, f"{d['score']}/10")
            p.setPen(QColor(T.MUTED))
            p.setFont(T.font(12))
            p.drawText(box.adjusted(12, 24, -12, -4), Qt.AlignLeft | Qt.AlignVCenter, sub)


class ActivityHeatmap(QWidget):
    """Last N weeks of study activity; columns fade in left to right."""
    CELL, GAP, LEFT, TOP = 13, 3, 30, 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self._weeks = 20
        self._days = {}
        self._t = 1.0
        self.setMouseTracking(True)
        step = self.CELL + self.GAP
        self.setMinimumSize(self.LEFT + 12 * step, self.TOP + 7 * step + 22)
        self._a = QVariantAnimation(self)
        self._a.setEasingCurve(QEasingCurve.OutCubic)
        self._a.valueChanged.connect(self._set)

    def resizeEvent(self, e):
        # show as many weeks as fit (12..53)
        self._weeks = max(12, min(53, (self.width() - self.LEFT) // (self.CELL + self.GAP)))
        super().resizeEvent(e)

    def _set(self, v):
        self._t = float(v)
        self.update()

    def set_days(self, days):
        self._days = days
        self._a.stop()
        self._a.setDuration(T.dur(900))
        self._a.setStartValue(0.0)
        self._a.setEndValue(1.0)
        self._a.start()
        if not T.MOTION["enabled"]:
            self._set(1.0)

    def _start(self):
        today = date.today()
        return today - timedelta(days=today.weekday()) - timedelta(weeks=self._weeks - 1)

    def _cell_rect(self, col, row):
        step = self.CELL + self.GAP
        return QRectF(self.LEFT + col * step, self.TOP + row * step, self.CELL, self.CELL)

    def _day_at(self, pos):
        step = self.CELL + self.GAP
        col = int((pos.x() - self.LEFT) // step)
        row = int((pos.y() - self.TOP) // step)
        if 0 <= col < self._weeks and 0 <= row < 7:
            d = self._start() + timedelta(weeks=col, days=row)
            if d <= date.today() and self._cell_rect(col, row).contains(pos):
                return d
        return None

    def mouseMoveEvent(self, e):
        d = self._day_at(e.position())
        if not d:
            QToolTip.hideText()
            return
        a = self._days.get(d.isoformat())
        if a:
            parts = [f"{v} {k if v != 1 else k.rstrip('s')}" for k, v in
                     (("practices", a["practices"]), ("reviews", a["reviews"]), ("quiz answers", a["quiz"])) if v]
            txt = f"{d.strftime('%a %d %b')}: " + ", ".join(parts)
        else:
            txt = f"{d.strftime('%a %d %b')}: no study"
        QToolTip.showText(e.globalPosition().toPoint(), txt, self)

    @staticmethod
    def _level(a):
        if not a:
            return 0
        n = a["practices"] * 5 + a["reviews"] + a["quiz"]
        return 1 if n < 5 else 2 if n < 12 else 3 if n < 25 else 4

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(T.mono_font(9, 0.5))
        start, today = self._start(), date.today()
        p.setPen(QColor(T.FAINT))
        for row, name in ((0, "MON"), (2, "WED"), (4, "FRI")):
            p.drawText(QRectF(0, self._cell_rect(0, row).top() - 2, self.LEFT - 6, self.CELL + 4),
                       Qt.AlignRight | Qt.AlignVCenter, name)
        last_month = None
        for col in range(self._weeks):
            d0 = start + timedelta(weeks=col)
            if d0.month != last_month:
                last_month = d0.month
                if col < self._weeks - 2:
                    p.setPen(QColor(T.FAINT))
                    p.drawText(QRectF(self._cell_rect(col, 0).left(), 0, 40, 14), Qt.AlignLeft, d0.strftime("%b").upper())
            alpha = max(0.0, min(1.0, (self._t * (self._weeks + 6) - col) / 6))
            for row in range(7):
                d = d0 + timedelta(days=row)
                if d > today:
                    continue
                lvl = self._level(self._days.get(d.isoformat()))
                self._dot(p, self._cell_rect(col, row), lvl, alpha, d == today)
        # legend
        y = self.TOP + 7 * (self.CELL + self.GAP) + 6
        x = self.LEFT + self._weeks * (self.CELL + self.GAP) - 5 * (self.CELL + self.GAP) - 34
        p.setPen(QColor(T.MUTED))
        p.drawText(QRectF(x - 40, y - 1, 36, self.CELL + 2), Qt.AlignRight | Qt.AlignVCenter, "LESS")
        for i in range(5):
            self._dot(p, QRectF(x + i * (self.CELL + self.GAP), y, self.CELL, self.CELL), i, 1.0, False)
        p.setPen(QColor(T.MUTED))
        p.drawText(QRectF(x + 5 * (self.CELL + self.GAP) + 2, y - 1, 40, self.CELL + 2),
                   Qt.AlignLeft | Qt.AlignVCenter, "MORE")

    @staticmethod
    def _dot(p, cell, lvl, alpha, today):
        """Empty days are tiny grey dots; active days grow and brighten to white. Today is ringed red."""
        c = QColor(T.FAINT) if lvl == 0 else T.mix(T.BORDER_HI, T.TEXT, (0.35, 0.6, 0.85, 1.0)[lvl - 1])
        c.setAlphaF(alpha)
        rad = (2.0, 3.6, 4.6, 5.6, 6.5)[lvl]
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(cell.center(), rad, rad)
        if today:
            p.setPen(QPen(QColor(T.RED), 1.4))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(cell.center(), cell.width() / 2 + 0.5, cell.width() / 2 + 0.5)
