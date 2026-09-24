"""Score calendar views, painted in dots: a month grid of score-colored day dots and a week of columns."""
import calendar
import math
from datetime import date, timedelta

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from .. import theme as T
from ..db import day_average

WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def fill_for(avg):
    """Day fill by average score: red < 5, grey 5–7, white 8–10 (text shows the number too)."""
    if avg is None:
        return None
    return QColor(T.RED if avg < 5 else T.MID if avg < 8 else T.TEXT)


def ink_for(avg):
    return QColor("#000000") if avg is not None and avg >= 5 else QColor(T.TEXT)


def tooltip_for(d, items):
    head = d.strftime("%a %d %b")
    if not items:
        return f"{head}: no practice"
    lines = [f"{head} · avg {day_average(items):.1f}/10" if day_average(items) is not None else head]
    for i in items:
        sc = "—" if i["score"] is None else f"{i['score']}/10"
        lines.append(f"{i['set_name']} · {i['name']}: {sc}")
    return "\n".join(lines)


class _Intro:
    """Pop-in animation shared by both views."""

    def _setup_intro(self):
        self._t = 1.0
        self._a = QVariantAnimation(self)
        self._a.setEasingCurve(QEasingCurve.OutBack)
        self._a.valueChanged.connect(self._tick)

    def _tick(self, v):
        self._t = float(v)
        self.update()

    def _play(self):
        self._a.stop()
        if not T.MOTION["enabled"]:
            self._tick(1.0)
            return
        self._a.setDuration(420)
        self._a.setStartValue(0.0)
        self._a.setEndValue(1.0)
        self._a.start()


class MonthGrid(QWidget, _Intro):
    daySelected = Signal(object)   # date
    HEAD = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_intro()
        self._year, self._month = date.today().year, date.today().month
        self._data = {}
        self._selected = None
        self._hover = None
        self.setMouseTracking(True)
        self.setMinimumHeight(360)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Month calendar. Arrow keys move the selected day, Enter opens it.")

    def set_month(self, year, month, data, selected=None):
        self._year, self._month, self._data = year, month, data
        self._selected = selected
        self._play()

    def selected(self):
        return self._selected

    def _days(self):
        """Six rows of seven dates, Monday first."""
        first = date(self._year, self._month, 1)
        start = first - timedelta(days=first.weekday())
        weeks = 6 if (first.weekday() + calendar.monthrange(self._year, self._month)[1]) > 35 else 5
        return [[start + timedelta(days=7 * r + c) for c in range(7)] for r in range(weeks)]

    def _cell(self, r, c, rows):
        w = self.width() / 7
        h = (self.height() - self.HEAD) / rows
        return QRectF(c * w, self.HEAD + r * h, w, h)

    def _at(self, pos):
        grid = self._days()
        rows = len(grid)
        for r in range(rows):
            for c in range(7):
                if self._cell(r, c, rows).contains(pos):
                    return grid[r][c]
        return None

    def mouseMoveEvent(self, e):
        d = self._at(e.position())
        if d != self._hover:
            self._hover = d
            self.update()
        if d:
            QToolTip.showText(e.globalPosition().toPoint(), tooltip_for(d, self._data.get(d.isoformat(), [])), self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        d = self._at(e.position())
        if d and e.button() == Qt.LeftButton:
            self._selected = d
            self.update()
            self.daySelected.emit(d)

    def keyPressEvent(self, e):
        step = {Qt.Key_Left: -1, Qt.Key_Right: 1, Qt.Key_Up: -7, Qt.Key_Down: 7}.get(e.key())
        if step:
            self._selected = (self._selected or date(self._year, self._month, 1)) + timedelta(days=step)
            self.daySelected.emit(self._selected)
            self.update()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter) and self._selected:
            self.daySelected.emit(self._selected)
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grid = self._days()
        rows = len(grid)
        w = self.width() / 7
        p.setFont(T.mono_font(10, 1.5))
        p.setPen(QColor(T.MUTED))
        for c, name in enumerate(WEEKDAYS):
            p.drawText(QRectF(c * w, 0, w, self.HEAD - 8), Qt.AlignCenter, name)
        today = date.today()
        for r, week in enumerate(grid):
            for c, d in enumerate(week):
                cell = self._cell(r, c, rows)
                items = self._data.get(d.isoformat(), [])
                avg = day_average(items)
                inside = d.month == self._month
                full = max(10.0, min(cell.width(), cell.height()) / 2 - 6)
                # staggered pop-in, left→right, top→bottom
                k = max(0.0, min(1.0, self._t * 1.6 - (r * 7 + c) / 70))
                rad = full * (0.4 + 0.6 * k)
                ctr = cell.center()
                fill = fill_for(avg)
                if fill is not None:
                    if not inside:
                        fill.setAlphaF(0.35)
                    p.setPen(Qt.NoPen)
                    p.setBrush(fill)
                    p.drawEllipse(ctr, rad, rad)
                elif items:
                    # practiced but unscored: hollow white ring
                    p.setPen(QPen(QColor(T.TEXT if inside else T.FAINT), 1.4))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(ctr, rad - 1, rad - 1)
                else:
                    # empty day: a ring of tiny dots
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(T.BORDER_HI if inside else T.BORDER))
                    for i in range(24):
                        a = 2 * math.pi * i / 24
                        p.drawEllipse(QPointF(ctr.x() + (rad - 1) * math.cos(a),
                                              ctr.y() + (rad - 1) * math.sin(a)), 0.9, 0.9)
                if d == self._hover or d == self._selected:
                    p.setPen(QPen(QColor(T.TEXT if d == self._selected else T.BORDER_HI), 1.2))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(ctr, full + 3.5, full + 3.5)
                if d == today:
                    p.setPen(QPen(QColor(T.RED), 2))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(ctr, full + 3.5, full + 3.5)
                # day number (dot-matrix) and average
                ink = ink_for(avg) if fill is not None and inside else QColor(T.TEXT if inside else T.FAINT)
                p.setPen(ink)
                p.setFont(T.dot_font(max(14, int(full * 0.62))))
                num_box = QRectF(ctr.x() - full, ctr.y() - full, 2 * full, 2 * full)
                p.drawText(num_box.adjusted(0, -full * 0.2 if avg is not None else 0, 0, 0),
                           Qt.AlignCenter, str(d.day))
                if avg is not None and inside:
                    p.setFont(T.mono_font(max(9, int(full * 0.26)), 0))
                    p.drawText(num_box.adjusted(0, full * 0.62, 0, 0), Qt.AlignCenter, f"{avg:.1f}")


class WeekView(QWidget, _Intro):
    """Seven columns; each practice is a pill colored by its score. Clicking a pill opens it."""
    practiceClicked = Signal(int)
    HEAD = 92
    PILL = 46

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_intro()
        self._start = date.today() - timedelta(days=date.today().weekday())
        self._data = {}
        self._hover = None
        self._pills = []    # (rect, practice_id)
        self.setMouseTracking(True)
        self.setMinimumHeight(360)

    def set_week(self, start, data):
        self._start, self._data = start, data
        self._play()

    def _pill_at(self, pos):
        for rect, pid in self._pills:
            if rect.contains(pos):
                return pid
        return None

    def mouseMoveEvent(self, e):
        pid = self._pill_at(e.position())
        if pid != self._hover:
            self._hover = pid
            self.setCursor(Qt.PointingHandCursor if pid else Qt.ArrowCursor)
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        pid = self._pill_at(e.position())
        if pid and e.button() == Qt.LeftButton:
            self.practiceClicked.emit(pid)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col_w = self.width() / 7
        today = date.today()
        self._pills = []
        for c in range(7):
            d = self._start + timedelta(days=c)
            items = self._data.get(d.isoformat(), [])
            avg = day_average(items)
            col = QRectF(c * col_w + 4, 0, col_w - 8, self.height())
            # column frame
            p.setPen(QPen(QColor(T.RED if d == today else T.BORDER), 1))
            p.setBrush(QColor(T.SURFACE))
            p.drawRoundedRect(col, 16, 16)
            # header: weekday + dot-matrix date + day average dot
            p.setFont(T.mono_font(10, 1.5))
            p.setPen(QColor(T.RED_TEXT if d == today else T.MUTED))
            p.drawText(QRectF(col.left(), 12, col.width(), 14), Qt.AlignCenter, WEEKDAYS[c])
            p.setFont(T.dot_font(30))
            p.setPen(QColor(T.TEXT))
            p.drawText(QRectF(col.left(), 26, col.width(), 34), Qt.AlignCenter, str(d.day))
            fill = fill_for(avg)
            k = max(0.0, min(1.0, self._t * 1.5 - c / 10))
            if fill is not None:
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
                p.drawEllipse(QPointF(col.center().x() - 20, 74), 5 * k, 5 * k)
                p.setFont(T.mono_font(11, 0))
                p.setPen(QColor(T.TEXT))
                p.drawText(QRectF(col.center().x() - 12, 64, 50, 20), Qt.AlignLeft | Qt.AlignVCenter,
                           f"{avg:.1f}")
            else:
                T.dotted_hline(p, col.center().x() - 16, col.center().x() + 16, 74, T.FAINT, 6, 1)
            # pills
            y = self.HEAD
            for it in items:
                if y + self.PILL > self.height() - 8:
                    p.setFont(T.mono_font(10, 0))
                    p.setPen(QColor(T.MUTED))
                    p.drawText(QRectF(col.left(), y, col.width(), 16), Qt.AlignCenter,
                               f"+{len(items) - items.index(it)} MORE")
                    break
                pill = QRectF(col.left() + 6, y, col.width() - 12, self.PILL - 6)
                pill.translate(0, (1 - k) * 12)
                hover = it["id"] == self._hover
                sc = it["score"]
                p.setPen(QPen(QColor(T.TEXT if hover else T.BORDER_HI), 1))
                p.setBrush(QColor(T.RAISED if hover else T.BG))
                p.drawRoundedRect(pill, 12, 12)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(T.score_color(sc)))
                p.drawEllipse(QPointF(pill.left() + 12, pill.top() + 12), 3.5, 3.5)
                p.setFont(T.mono_font(11, 0))
                p.setPen(QColor(T.score_color(sc) if sc is not None else T.MUTED))
                p.drawText(QRectF(pill.left() + 20, pill.top() + 3, pill.width() - 24, 18),
                           Qt.AlignLeft | Qt.AlignVCenter, "—" if sc is None else f"{sc}/10")
                p.setFont(T.font(11))
                p.setPen(QColor(T.MUTED))
                txt = p.fontMetrics().elidedText(f"{it['name']} · {it['set_name']}", Qt.ElideRight,
                                                 int(pill.width() - 16))
                p.drawText(QRectF(pill.left() + 8, pill.top() + 20, pill.width() - 12, 18),
                           Qt.AlignLeft | Qt.AlignVCenter, txt)
                self._pills.append((pill, it["id"]))
                y += self.PILL
            if not items:
                p.setFont(T.mono_font(10, 1))
                p.setPen(QColor(T.FAINT))
                p.drawText(QRectF(col.left(), self.HEAD, col.width(), 20), Qt.AlignCenter, "REST")
