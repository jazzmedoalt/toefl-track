"""Breakpoint charts, painted in dots: reason ranking, reason-by-week timeline, reason × type matrix."""
import math
from datetime import timedelta

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from .. import db
from .. import theme as T


def _grow(widget):
    """Shared 0→1 intro animation (instant with reduced motion)."""
    widget._t = 1.0
    a = QVariantAnimation(widget, startValue=0.0, endValue=1.0, duration=600, easingCurve=QEasingCurve.OutCubic)

    def tick(v):
        widget._t = float(v)
        widget.update()
    a.valueChanged.connect(tick)
    return a


def _play(a):
    a.stop()
    if T.MOTION["enabled"]:
        a.start()
    else:
        a.valueChanged.emit(1.0)


class ReasonBars(QWidget):
    """One row per reason: icon, name, dot bar of its share, count and quiz accuracy.
    The breakpoint row is red. Click (or ↑/↓) selects a reason."""
    selected = Signal(str)
    ROW = 46
    NAME_W = 230

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows, self._sel, self._hover, self._top = [], None, None, None
        self._a = _grow(self)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName("Reasons ranked by how often they caught you. Arrow keys change the selection.")

    def set_data(self, rows, top_key, selected_key):
        self._rows = sorted(rows, key=lambda r: -r["count"])
        self._top, self._sel = top_key, selected_key
        self.setFixedHeight(self.ROW * len(self._rows) + 4)
        _play(self._a)

    def select(self, key):
        self._sel = key
        self.update()
        self.selected.emit(key)

    def _row_at(self, y):
        i = int(y // self.ROW)
        return self._rows[i] if 0 <= i < len(self._rows) else None

    def mouseMoveEvent(self, e):
        r = self._row_at(e.position().y())
        key = r["key"] if r else None
        if key != self._hover:
            self._hover = key
            self.update()
        if r:
            acc = "not quizzed yet" if r["accuracy"] is None else f"quiz accuracy {r['accuracy'] * 100:.0f}%"
            QToolTip.showText(e.globalPosition().toPoint(), f"{r['name']}\n{r['desc']}\n{r['count']} mistakes · {acc}",
                              self)

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        r = self._row_at(e.position().y())
        if r and e.button() == Qt.LeftButton:
            self.select(r["key"])

    def keyPressEvent(self, e):
        keys = [r["key"] for r in self._rows]
        if e.key() in (Qt.Key_Up, Qt.Key_Down) and keys:
            i = keys.index(self._sel) if self._sel in keys else -1
            i = max(0, min(len(keys) - 1, i + (1 if e.key() == Qt.Key_Down else -1)))
            self.select(keys[i])
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        mx = max([r["count"] for r in self._rows] + [1])
        for i, r in enumerate(self._rows):
            y = i * self.ROW
            row = QRectF(0, y + 2, w, self.ROW - 4)
            if r["key"] == self._sel or r["key"] == self._hover:
                p.setPen(QPen(QColor(T.BORDER_HI if r["key"] == self._sel else T.BORDER), 1))
                p.setBrush(QColor(T.RAISED if r["key"] == self._sel else T.HOVER))
                p.drawRoundedRect(row, 14, 14)
            top = r["key"] == self._top
            ic = T.icon_pixmap(r["icon"], T.RED if top else T.MUTED, 18)
            p.drawPixmap(QPointF(12, row.center().y() - 9), ic)
            p.setFont(T.font(13, QFont.DemiBold if top else QFont.Normal))
            p.setPen(QColor(T.TEXT if r["count"] else T.MUTED))
            name = p.fontMetrics().elidedText(r["name"], Qt.ElideRight, self.NAME_W - 44)
            p.drawText(QRectF(40, row.top(), self.NAME_W - 44, row.height()), Qt.AlignVCenter | Qt.AlignLeft, name)
            # count + accuracy on the right
            right = QRectF(w - 110, row.top(), 98, row.height())
            p.setFont(T.dot_font(22))
            p.setPen(QColor(T.RED if top else T.TEXT if r["count"] else T.FAINT))
            p.drawText(right.adjusted(0, 0, -44, 0), Qt.AlignVCenter | Qt.AlignRight, str(r["count"]))
            p.setFont(T.mono_font(10, 0.5))
            p.setPen(QColor(T.MUTED))
            acc = "—" if r["accuracy"] is None else f"{r['accuracy'] * 100:.0f}%"
            p.drawText(right.adjusted(60, 0, 0, 0), Qt.AlignVCenter | Qt.AlignRight, acc)
            # dot bar
            bar = QRectF(self.NAME_W, row.center().y() - 4, max(10, w - self.NAME_W - 130), 8)
            T.dot_row(p, bar, r["count"] / mx * self._t, T.RED if top else T.TEXT, T.BORDER_HI, 9)
        if self.hasFocus() and self._sel:
            keys = [r["key"] for r in self._rows]
            if self._sel in keys:
                p.setPen(QPen(QColor(T.RED), 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(QRectF(1, keys.index(self._sel) * self.ROW + 3, w - 2, self.ROW - 6), 14, 14)


class ReasonTimeline(QWidget):
    """Dot matrix: reasons down, weeks across. Bigger, brighter dot = more mistakes that week."""
    LABEL_W = 230
    ROW = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start, self._data, self._sel = None, {}, None
        self._a = _grow(self)
        self.setMouseTracking(True)
        self.setAccessibleName("Mistakes per reason per week")

    def set_data(self, start, data, selected_key):
        self._start, self._data, self._sel = start, data, selected_key
        self.setFixedHeight(self.ROW * len(db.REASONS) + 26)
        _play(self._a)

    def set_selected(self, key):
        self._sel = key
        self.update()

    def _geom(self):
        weeks = len(next(iter(self._data.values()), [0] * 8))
        cw = (self.width() - self.LABEL_W) / max(1, weeks)
        return weeks, cw

    def mouseMoveEvent(self, e):
        if not self._data:
            return
        weeks, cw = self._geom()
        x, y = e.position().x() - self.LABEL_W, e.position().y()
        r, c = int(y // self.ROW), int(x // cw) if x >= 0 else -1
        if 0 <= r < len(db.REASONS) and 0 <= c < weeks:
            key = db.REASONS[r][0]
            wk = self._start + timedelta(weeks=c)
            n = self._data[key][c]
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"{db.REASONS[r][1]}\nweek of {wk.strftime('%d %b')}: {n} mistake{'s' * (n != 1)}", self)
        else:
            QToolTip.hideText()

    def paintEvent(self, _):
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        weeks, cw = self._geom()
        mx = max([max(v) for v in self._data.values()] + [1])
        maxr = min(cw, self.ROW) / 2 - 3
        for r, (key, name, icon, *_rest) in enumerate(db.REASONS):
            cy = r * self.ROW + self.ROW / 2
            sel = key == self._sel
            p.drawPixmap(QPointF(0, cy - 8), T.icon_pixmap(icon, T.RED if sel else T.MUTED, 16))
            p.setFont(T.font(12, QFont.DemiBold if sel else QFont.Normal))
            p.setPen(QColor(T.TEXT if sel else T.MUTED))
            p.drawText(QRectF(24, cy - 10, self.LABEL_W - 30, 20), Qt.AlignVCenter | Qt.AlignLeft,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, self.LABEL_W - 30))
            for c in range(weeks):
                n = self._data[key][c]
                cx = self.LABEL_W + c * cw + cw / 2
                p.setPen(Qt.NoPen)
                if n == 0:
                    p.setBrush(QColor(T.BORDER_HI))
                    p.drawEllipse(QPointF(cx, cy), 1.3, 1.3)
                    continue
                k = math.sqrt(n / mx)
                col = QColor(T.RED if sel else T.TEXT)
                col.setAlphaF(1.0 if sel else 0.35 + 0.65 * k)
                p.setBrush(col)
                rad = (2.5 + (maxr - 2.5) * k) * self._t
                p.drawEllipse(QPointF(cx, cy), rad, rad)
        # week labels
        p.setFont(T.mono_font(10, 0.5))
        p.setPen(QColor(T.MUTED))
        y = len(db.REASONS) * self.ROW + 4
        for c in range(weeks):
            if (c % 3 == 0 and c < weeks - 2) or c == weeks - 1:
                wk = self._start + timedelta(weeks=c)
                txt = "THIS WK" if c == weeks - 1 else wk.strftime("%d %b").upper()
                p.drawText(QRectF(self.LABEL_W + c * cw - 10, y, cw + 20, 18), Qt.AlignCenter, txt)


class ReasonMatrix(QWidget):
    """Reasons down, mistake types across; dot size = count. The biggest cell gets a red ring."""
    LABEL_W = 230
    ROW = 30
    HEAD = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cells, self._types, self._sel = {}, [], None
        self._a = _grow(self)
        self.setMouseTracking(True)
        self.setAccessibleName("Which mistake types each reason shows up in")

    def set_data(self, cells, types, selected_key):
        self._cells, self._types, self._sel = cells, types[:7], selected_key
        self.setFixedHeight(self.HEAD + self.ROW * len(db.REASONS) + 4)
        _play(self._a)

    def set_selected(self, key):
        self._sel = key
        self.update()

    def _cw(self):
        return (self.width() - self.LABEL_W) / max(1, len(self._types))

    def mouseMoveEvent(self, e):
        cw = self._cw()
        x, y = e.position().x() - self.LABEL_W, e.position().y() - self.HEAD
        r, c = int(y // self.ROW) if y >= 0 else -1, int(x // cw) if x >= 0 else -1
        if 0 <= r < len(db.REASONS) and 0 <= c < len(self._types):
            n = self._cells.get((db.REASONS[r][0], self._types[c]), 0)
            QToolTip.showText(e.globalPosition().toPoint(), f"{db.REASONS[r][1]} in {self._types[c]}: {n}", self)
        else:
            QToolTip.hideText()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self._types:
            return
        cw = self._cw()
        mx = max(list(self._cells.values()) + [1])
        biggest = max(self._cells, key=self._cells.get) if self._cells else None
        p.setFont(T.mono_font(10, 0.5))
        p.setPen(QColor(T.MUTED))
        for c, t in enumerate(self._types):
            p.drawText(QRectF(self.LABEL_W + c * cw, 0, cw, self.HEAD - 6), Qt.AlignCenter,
                       p.fontMetrics().elidedText(t.upper(), Qt.ElideRight, int(cw - 4)))
        maxr = min(cw, self.ROW) / 2 - 3
        for r, (key, name, icon, *_rest) in enumerate(db.REASONS):
            cy = self.HEAD + r * self.ROW + self.ROW / 2
            sel = key == self._sel
            p.drawPixmap(QPointF(0, cy - 8), T.icon_pixmap(icon, T.RED if sel else T.MUTED, 16))
            p.setFont(T.font(12, QFont.DemiBold if sel else QFont.Normal))
            p.setPen(QColor(T.TEXT if sel else T.MUTED))
            p.drawText(QRectF(24, cy - 10, self.LABEL_W - 30, 20), Qt.AlignVCenter | Qt.AlignLeft,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, self.LABEL_W - 30))
            for c, t in enumerate(self._types):
                n = self._cells.get((key, t), 0)
                cx = self.LABEL_W + c * cw + cw / 2
                p.setPen(Qt.NoPen)
                if not n:
                    p.setBrush(QColor(T.BORDER_HI))
                    p.drawEllipse(QPointF(cx, cy), 1.3, 1.3)
                    continue
                k = math.sqrt(n / mx)
                col = QColor(T.RED if sel else T.TEXT)
                col.setAlphaF(1.0 if sel else 0.35 + 0.65 * k)
                p.setBrush(col)
                rad = (2.5 + (maxr - 2.5) * k) * self._t
                p.drawEllipse(QPointF(cx, cy), rad, rad)
                if (key, t) == biggest:
                    p.setPen(QPen(QColor(T.RED), 1.5))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(QPointF(cx, cy), maxr + 2, maxr + 2)
