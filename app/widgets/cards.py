"""Painted, animated building blocks in the Nothing OS style: hairline cards, dot-matrix numbers,
dot rings, dot progress rows, dot score picker, pills, toggle and the flip card."""
import math

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from .. import theme as T


def label(text="", role=None, parent=None) -> QLabel:
    lb = QLabel(text, parent)
    if role:
        lb.setProperty("role", role)
    return lb


def button(text="", kind=None, icon_name=None, icon_color=None, parent=None) -> QPushButton:
    b = QPushButton(text, parent)
    if kind:
        b.setProperty("kind", kind)
    if icon_name:
        color = icon_color or ("#000000" if kind == "primary" else T.MUTED)
        b.setIcon(T.icon(icon_name, color, 16))
        b.setIconSize(QSize(16, 16))
    b.setCursor(Qt.PointingHandCursor)
    return b


def _anim(parent, on_value, ms=180, curve=QEasingCurve.OutCubic) -> QVariantAnimation:
    a = QVariantAnimation(parent)
    a.setEasingCurve(curve)
    a.setDuration(ms)
    a.valueChanged.connect(on_value)
    return a


def _run(a: QVariantAnimation, start, end, ms, apply):
    """Start an animation, or jump straight to the end with reduced motion."""
    a.stop()
    if not T.MOTION["enabled"]:
        apply(end)
        return
    a.setDuration(ms)
    a.setStartValue(start)
    a.setEndValue(end)
    a.start()


class Card(QFrame):
    """Black surface with a hairline border. Clickable cards brighten on hover; keyboard focus is red."""
    clicked = Signal()

    def __init__(self, parent=None, clickable=False, radius=18, padding=18):
        super().__init__(parent)
        self._clickable = clickable
        self._radius = radius
        self._hover = 0.0
        self._hover_anim = _anim(self, self._set_hover)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(padding, padding, padding, padding)
        lay.setSpacing(10)
        if clickable:
            self.setCursor(Qt.PointingHandCursor)
            self.setFocusPolicy(Qt.StrongFocus)

    def _set_hover(self, v):
        self._hover = float(v)
        self.update()

    def enterEvent(self, e):
        if self._clickable:
            _run(self._hover_anim, self._hover, 1.0, 180, self._set_hover)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._clickable:
            _run(self._hover_anim, self._hover, 0.0, 180, self._set_hover)
        super().leaveEvent(e)

    def focusInEvent(self, e):
        self.update()
        super().focusInEvent(e)

    def focusOutEvent(self, e):
        self.update()
        super().focusOutEvent(e)

    def mouseReleaseEvent(self, e):
        if self._clickable and e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if self._clickable and e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(T.mix(T.SURFACE, T.RAISED, self._hover))
        border = T.mix(T.BORDER, T.BORDER_HI, self._hover)
        if self._clickable and self.hasFocus():
            border = QColor(T.RED)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(r, self._radius, self._radius)


class IconBadge(QWidget):
    """Hairline circle holding a glyph icon."""

    def __init__(self, icon_name, color=T.TEXT, size=34, parent=None):
        super().__init__(parent)
        self._icon = max(16, round(size * 0.46))
        self._pm = T.icon_pixmap(icon_name, color, self._icon)
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(T.BORDER_HI), 1))
        p.setBrush(QColor(T.BG))
        p.drawEllipse(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        x = (self.width() - self._icon) / 2
        p.drawPixmap(QPointF(x, x), self._pm)


class StatCard(Card):
    """Nothing-style widget: mono label, glyph, and a big dot-matrix number that counts up."""

    def __init__(self, title, icon_name, color=T.MUTED, parent=None, clickable=False):
        super().__init__(parent, clickable=clickable, padding=16)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(label(title.upper(), "eyebrow"), 1)
        glyph = QLabel()
        glyph.setPixmap(T.icon_pixmap(icon_name, color, 18))
        top.addWidget(glyph)
        self.layout().addLayout(top)
        self.value = label("—", "display")
        self.value.setMinimumHeight(52)
        self.sub = label("", "caption")
        self.layout().addWidget(self.value)
        self.layout().addWidget(self.sub)
        self._fmt = "{:.0f}"
        self._count = _anim(self, lambda v: self.value.setText(self._fmt.format(v)), 700)

    def set_value(self, v, fmt="{:.0f}", sub="", accent=False):
        self.sub.setText(sub)
        self.value.setStyleSheet(f"color: {T.RED};" if accent else "")  # keeps the role's dot font
        if v is None:
            self._count.stop()
            self.value.setText("—")
            return
        self._fmt = fmt
        _run(self._count, 0.0, float(v), 700, lambda x: self.value.setText(fmt.format(x)))


class ScoreRing(QWidget):
    """A ring of dots that light up to the 0–10 value; the leading dot is red."""
    DOTS = 40

    def __init__(self, parent=None, size=150):
        super().__init__(parent)
        self._value = 0.0
        self._target = None
        self.setMinimumSize(size, size)
        self._a = _anim(self, self._set, 900)

    def _set(self, v):
        self._value = float(v)
        self.update()

    def set_value(self, v):
        self._target = v
        _run(self._a, 0.0, float(v or 0), 900, self._set)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 12
        c = QPointF(self.width() / 2, self.height() / 2)
        radius = side / 2 - 5
        lit = int(round(self._value / 10 * self.DOTS)) if self._target is not None else 0
        p.setPen(Qt.NoPen)
        for i in range(self.DOTS):
            a = -math.pi / 2 + 2 * math.pi * i / self.DOTS
            pt = QPointF(c.x() + radius * math.cos(a), c.y() + radius * math.sin(a))
            if i < lit:
                p.setBrush(QColor(T.RED if i == lit - 1 else T.TEXT))
                p.drawEllipse(pt, 4, 4)
            else:
                p.setBrush(QColor(T.FAINT))
                p.drawEllipse(pt, 2.5, 2.5)
        box = QRectF(c.x() - side / 2, c.y() - side / 2, side, side)
        p.setPen(QColor(T.TEXT))
        p.setFont(T.dot_font(int(side * 0.28)))
        txt = "—" if self._target is None else f"{self._value:.1f}"
        p.drawText(box.adjusted(0, -side * 0.08, 0, 0), Qt.AlignCenter, txt)
        p.setPen(QColor(T.MUTED))
        p.setFont(T.mono_font(10))
        p.drawText(box.adjusted(0, side * 0.3, 0, 0), Qt.AlignCenter, "AVG / 10")


class ScorePill(QWidget):
    """Hairline pill: score dot + 'x/10'. The text always carries the value."""

    def __init__(self, score=None, parent=None):
        super().__init__(parent)
        self._score = score
        self.setFixedSize(66, 24)

    def set_score(self, s):
        self._score = s
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(T.score_color(self._score))
        p.setPen(QPen(QColor(T.BORDER_HI), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPointF(13, self.height() / 2), 3.5, 3.5)
        p.setPen(c)
        p.setFont(T.mono_font(12, 0))
        p.drawText(QRectF(20, 0, self.width() - 24, self.height()), Qt.AlignCenter,
                   "—" if self._score is None else f"{self._score}/10")


class CategoryBars(QWidget):
    """Mistake categories as rows of dots; the top category is red."""
    ROW = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._t = 1.0
        self._a = _anim(self, self._set, 700)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def _set(self, v):
        self._t = float(v)
        self.update()

    def set_items(self, items):
        self._items = items
        self.setMinimumHeight(max(1, len(items)) * self.ROW)
        _run(self._a, 0.0, 1.0, 700, self._set)
        self.updateGeometry()

    def paintEvent(self, _):
        if not self._items:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        top = max(n for _, n in self._items)
        label_w = 110
        bar_x = label_w + 8
        bar_w = self.width() - bar_x - 36
        for i, (name, n) in enumerate(self._items):
            y = i * self.ROW
            p.setFont(T.font(13))
            p.setPen(QColor(T.TEXT))
            p.drawText(QRectF(0, y, label_w, self.ROW), Qt.AlignVCenter | Qt.AlignLeft,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, label_w))
            T.dot_row(p, QRectF(bar_x, y + self.ROW / 2 - 3.5, bar_w, 7), n / top * self._t,
                      on=T.RED if i == 0 else T.TEXT)
            p.setFont(T.mono_font(12, 0))
            p.setPen(QColor(T.MUTED))
            p.drawText(QRectF(bar_x + bar_w, y, 36, self.ROW), Qt.AlignVCenter | Qt.AlignRight, str(n))


class Toggle(QAbstractButton):
    """On/off switch: hairline pill, red when on."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 24)
        self._pos = 0.0
        self._a = _anim(self, self._set, 160)
        self.toggled.connect(lambda on: _run(self._a, self._pos, 1.0 if on else 0.0, 160, self._set))

    def _set(self, v):
        self._pos = float(v)
        self.update()

    def setChecked(self, on):
        super().setChecked(on)
        self._set(1.0 if on else 0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(T.TEXT if self.hasFocus() else T.BORDER_HI), 1))
        p.setBrush(T.mix(T.BG, T.RED, self._pos))
        p.drawRoundedRect(track, 11, 11)
        p.setPen(Qt.NoPen)
        p.setBrush(T.mix(T.MUTED, T.TEXT, self._pos))
        x = 5 + self._pos * (self.width() - 24)
        p.drawEllipse(QRectF(x, 5, 14, 14))


class ScorePicker(QWidget):
    """0–10 as a row of dots; the chosen one fills with its score color. Keyboard: ←/→, 0–9."""
    valueChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = None
        self._pos = 0.0
        self._hover = -1
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setMinimumWidth(11 * 36)
        self._a = _anim(self, self._set, 220)

    def _set(self, v):
        self._pos = float(v)
        self.update()

    def value(self):
        return self._value

    def setValue(self, v, animate=True, emit=False):
        had = self._value is not None
        self._value = v
        if v is not None:
            if animate and had:
                _run(self._a, self._pos, float(v), 220, self._set)
            else:
                self._set(float(v))
        self.update()
        if emit:
            self.valueChanged.emit(v)

    def _center(self, i):
        w = self.width() / 11
        return QPointF(i * w + w / 2, self.height() / 2)

    def _index_at(self, x):
        return max(0, min(10, int(x / (self.width() / 11))))

    def mouseMoveEvent(self, e):
        i = self._index_at(e.position().x())
        if i != self._hover:
            self._hover = i
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.setValue(self._index_at(e.position().x()), emit=True)

    def keyPressEvent(self, e):
        k = e.key()
        cur = self._value if self._value is not None else 0
        if k in (Qt.Key_Left, Qt.Key_Down):
            self.setValue(max(0, cur - 1), emit=True)
        elif k in (Qt.Key_Right, Qt.Key_Up):
            self.setValue(min(10, cur + 1 if self._value is not None else 0), emit=True)
        elif Qt.Key_0 <= k <= Qt.Key_9:
            self.setValue(k - Qt.Key_0, emit=True)
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rad = min(self.height() / 2 - 3, self.width() / 22 - 3)
        if self.hasFocus():
            p.setPen(QPen(QColor(T.BORDER_HI), 1, Qt.DotLine))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), rad + 3, rad + 3)
        # connecting dotted track
        T.dotted_hline(p, self._center(0).x(), self._center(10).x(), self.height() / 2, T.BORDER_HI, 5, 0.8)
        for i in range(11):
            c = self._center(i)
            p.setPen(QPen(QColor(T.TEXT if i == self._hover else T.BORDER_HI), 1))
            p.setBrush(QColor(T.BG))
            p.drawEllipse(c, rad, rad)
        if self._value is not None:
            c = QPointF(self._center(0).x() + (self._center(10).x() - self._center(0).x()) * self._pos / 10,
                        self.height() / 2)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T.score_color(round(self._pos))))
            p.drawEllipse(c, rad, rad)
        p.setFont(T.mono_font(13, 0))
        for i in range(11):
            selected = self._value is not None and abs(self._pos - i) < 0.5
            dark = selected and T.score_color(i) != T.RED_TEXT
            p.setPen(QColor("#000000" if dark else T.TEXT if selected or i == self._hover else T.MUTED))
            c = self._center(i)
            p.drawText(QRectF(c.x() - rad, c.y() - rad, 2 * rad, 2 * rad), Qt.AlignCenter, str(i))


class EmptyState(QWidget):
    def __init__(self, icon_name, title, text, action_text=None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(8)
        lay.addWidget(IconBadge(icon_name, T.RED, 56), 0, Qt.AlignHCenter)
        lay.addSpacing(6)
        t = label(title, "h2")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        d = label(text, "muted")
        d.setAlignment(Qt.AlignCenter)
        d.setWordWrap(True)
        d.setFixedWidth(360)
        lay.addWidget(d, 0, Qt.AlignHCenter)
        self.action = None
        if action_text:
            lay.addSpacing(6)
            self.action = button(action_text, "primary", "plus")
            lay.addWidget(self.action, 0, Qt.AlignHCenter)


class ProgressBar(QWidget):
    """Row of dots that fills to its value (0..1); the leading dot is red."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._v = 0.0
        self.setFixedHeight(8)
        self._a = _anim(self, self._set, 300)

    def _set(self, v):
        self._v = float(v)
        self.update()

    def set_value(self, v):
        _run(self._a, self._v, float(v), 300, self._set)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pitch = 8.0
        n = max(1, int(self.width() // pitch))
        lit = round(n * max(0.0, min(1.0, self._v)))
        p.setPen(Qt.NoPen)
        for i in range(n):
            if i < lit:
                p.setBrush(QColor(T.RED if i == lit - 1 and lit < n else T.TEXT))
                p.drawEllipse(QPointF(pitch * i + pitch / 2, 4), 3, 3)
            else:
                p.setBrush(QColor(T.FAINT))
                p.drawEllipse(QPointF(pitch * i + pitch / 2, 4), 1.6, 1.6)


class FlipCard(QWidget):
    """Flashcard that flips (x-scale) between the word and its meaning. Click or Space flips it."""
    flipped = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._card = None
        self._back = False
        self._t = 0.0        # 0 = front, 1 = back
        self.setMinimumHeight(260)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Flashcard, press Space to flip")
        self._a = _anim(self, self._set, 320, QEasingCurve.InOutCubic)

    def _set(self, v):
        self._t = float(v)
        self.update()

    def set_card(self, card):
        self._card = card
        self._back = False
        self._a.stop()
        self._set(0.0)

    def is_back(self):
        return self._back

    def flip(self):
        if not self._card:
            return
        self._back = not self._back
        _run(self._a, self._t, 1.0 if self._back else 0.0, 320, self._set)
        self.flipped.emit(self._back)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.flip()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.flip()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = min(self.width() - 4, 620)
        r = QRectF((self.width() - w) / 2, 2, w, self.height() - 4)
        sx = abs(math.cos(math.pi * self._t))
        back = self._t > 0.5
        c = r.center()
        p.translate(c)
        p.scale(max(sx, 0.001), 1)
        p.translate(-c)
        p.setPen(QPen(QColor(T.RED if self.hasFocus() else T.BORDER_HI), 1))
        p.setBrush(QColor(T.SURFACE if back else T.BG))
        p.drawRoundedRect(r, 22, 22)
        if not self._card:
            return
        inner = r.adjusted(28, 22, -28, -22)
        # corner labels + red dot, like a Nothing widget
        p.setFont(T.mono_font(11, 1.5))
        p.setPen(QColor(T.MUTED))
        p.drawText(inner, Qt.AlignTop | Qt.AlignLeft, "MEANING" if back else "WORD")
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.RED))
        p.drawEllipse(QPointF(inner.right() - 4, inner.top() + 7), 4, 4)
        if not back:
            p.setPen(QColor(T.TEXT))
            p.setFont(T.dot_font(52))
            p.drawText(inner, Qt.AlignCenter | Qt.TextWordWrap, self._card["word"])
            p.setPen(QColor(T.FAINT))
            p.setFont(T.mono_font(11, 1))
            p.drawText(inner, Qt.AlignBottom | Qt.AlignHCenter, "CLICK OR SPACE TO FLIP")
            return
        body = inner.adjusted(0, 26, 0, -24)
        meaning = self._card["meaning"] or "(no meaning yet — add one in the word list)"
        italic = T.font(15)
        italic.setItalic(True)
        blocks = [(meaning, T.font(24, QFont.DemiBold), T.TEXT)]
        if self._card["example"]:
            blocks.append((f"“{self._card['example']}”", italic, T.MUTED))
        if self._card["synonyms"]:
            blocks.append(("≈ " + self._card["synonyms"].upper(), T.mono_font(12, 1), T.RED_TEXT))
        heights = []
        for text, fnt, _ in blocks:
            p.setFont(fnt)
            heights.append(p.boundingRect(body, Qt.AlignHCenter | Qt.TextWordWrap, text).height())
        gap = 14
        y = body.top() + max(0.0, (body.height() - sum(heights) - gap * (len(blocks) - 1)) / 2)
        for (text, fnt, color), h in zip(blocks, heights):
            p.setFont(fnt)
            p.setPen(QColor(color))
            p.drawText(QRectF(body.left(), y, body.width(), h), Qt.AlignHCenter | Qt.TextWordWrap, text)
            y += h + gap
        p.setPen(QColor(T.FAINT))
        p.setFont(T.dot_font(18))
        p.drawText(inner, Qt.AlignBottom | Qt.AlignHCenter, self._card["word"])


def shake(widget):
    """Short horizontal shake for a wrong answer (skipped with reduced motion)."""
    if not T.MOTION["enabled"]:
        return
    start = widget.pos()
    a = QPropertyAnimation(widget, b"pos", widget)
    a.setDuration(360)
    for i, dx in enumerate((0, -8, 8, -6, 6, -3, 3, 0)):
        a.setKeyValueAt(i / 7, start + QPoint(dx, 0))
    a.start(QPropertyAnimation.DeleteWhenStopped)
