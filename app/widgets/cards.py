"""Painted, animated building blocks: cards, stat tiles, score ring/pill/picker, bars, toggle."""
import math

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
                            QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPen
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
        color = icon_color or ("#FFFFFF" if kind == "primary" else T.MUTED)
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


class Card(QFrame):
    """Rounded surface. Clickable cards animate their border/background on hover and focus."""
    clicked = Signal()

    def __init__(self, parent=None, clickable=False, radius=14, padding=18):
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

    def _animate_hover(self, target):
        self._hover_anim.stop()
        self._hover_anim.setDuration(T.dur(180))
        self._hover_anim.setStartValue(self._hover)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def enterEvent(self, e):
        if self._clickable:
            self._animate_hover(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._clickable:
            self._animate_hover(0.0)
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
        p.setBrush(T.mix(T.SURFACE, T.RAISED, self._hover * 0.7))
        border = T.mix(T.BORDER, T.BORDER_HI, self._hover)
        if self._clickable and self.hasFocus():
            border = QColor(T.ACCENT)
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(r, self._radius, self._radius)


class IconBadge(QWidget):
    """Tinted rounded square holding an icon."""

    def __init__(self, icon_name, color=T.ACCENT, size=34, parent=None):
        super().__init__(parent)
        self._icon = max(18, round(size * 0.46))
        self._pm = T.icon_pixmap(icon_name, color, self._icon)
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QColor(self._color)
        bg.setAlphaF(0.14)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()), max(9, self.width() * 0.26), max(9, self.width() * 0.26))
        x = (self.width() - self._icon) / 2
        p.drawPixmap(QPointF(x, x), self._pm)


class StatCard(Card):
    """Stat tile whose number counts up when set."""

    def __init__(self, title, icon_name, color=T.ACCENT, parent=None, clickable=False):
        super().__init__(parent, clickable=clickable, padding=16)
        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(IconBadge(icon_name, color))
        top.addWidget(label(title.upper(), "eyebrow"), 1)
        self.layout().addLayout(top)
        self.value = label("—")
        f = QFont(T.FONT)
        f.setPixelSize(28)
        f.setWeight(QFont.DemiBold)
        self.value.setFont(f)
        self.sub = label("", "caption")
        self.layout().addWidget(self.value)
        self.layout().addWidget(self.sub)
        self._fmt = "{:.0f}"
        self._count = _anim(self, lambda v: self.value.setText(self._fmt.format(v)), 700)

    def set_value(self, v, fmt="{:.0f}", sub=""):
        self.sub.setText(sub)
        if v is None:
            self._count.stop()
            self.value.setText("—")
            return
        self._fmt = fmt
        self._count.stop()
        self._count.setDuration(T.dur(700))
        self._count.setStartValue(0.0)
        self._count.setEndValue(float(v))
        self._count.start()
        if not T.MOTION["enabled"]:
            self.value.setText(fmt.format(v))


class ScoreRing(QWidget):
    """Animated circular gauge for a 0–10 value."""

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
        self._a.stop()
        self._a.setDuration(T.dur(900))
        self._a.setStartValue(0.0)
        self._a.setEndValue(float(v or 0))
        self._a.start()
        if not T.MOTION["enabled"]:
            self._set(v or 0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 14
        r = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        p.setPen(QPen(QColor(T.BORDER), 11, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 0, 360 * 16)
        if self._target is not None and self._value > 0:
            grad = QConicalGradient(r.center(), 90)
            grad.setColorAt(0.0, QColor(T.ACCENT))
            grad.setColorAt(0.5, QColor(T.ACCENT_2))
            grad.setColorAt(1.0, QColor(T.ACCENT))
            p.setPen(QPen(grad, 11, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, 90 * 16, -int(self._value / 10 * 360 * 16))
        p.setPen(QColor(T.TEXT))
        f = QFont(T.FONT)
        f.setPixelSize(int(side * 0.24))
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        txt = "—" if self._target is None else f"{self._value:.1f}"
        p.drawText(r.adjusted(0, -side * 0.08, 0, 0), Qt.AlignCenter, txt)
        f.setPixelSize(12)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        p.setPen(QColor(T.MUTED))
        p.drawText(r.adjusted(0, side * 0.26, 0, 0), Qt.AlignCenter, "average / 10")


class ScorePill(QWidget):
    """Colored '8/10' chip. Text always carries the value, so color is never the only cue."""

    def __init__(self, score=None, parent=None):
        super().__init__(parent)
        self._score = score
        self.setFixedSize(58, 24)

    def set_score(self, s):
        self._score = s
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(T.score_color(self._score))
        bg = QColor(c)
        bg.setAlphaF(0.14)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()), 12, 12)
        p.setPen(c)
        f = QFont(T.FONT)
        f.setPixelSize(12)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, "—" if self._score is None else f"{self._score}/10")


class CategoryBars(QWidget):
    """Horizontal bars for mistake categories, growing in on update."""
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
        self._a.stop()
        self._a.setDuration(T.dur(700))
        self._a.setStartValue(0.0)
        self._a.setEndValue(1.0)
        self._a.start()
        self.updateGeometry()

    def paintEvent(self, _):
        if not self._items:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(T.FONT)
        f.setPixelSize(13)
        p.setFont(f)
        top = max(n for _, n in self._items)
        label_w = 110
        bar_x = label_w + 8
        bar_w = self.width() - bar_x - 36
        for i, (name, n) in enumerate(self._items):
            y = i * self.ROW
            p.setPen(QColor(T.TEXT))
            p.drawText(QRectF(0, y, label_w, self.ROW), Qt.AlignVCenter | Qt.AlignLeft,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, label_w))
            track = QRectF(bar_x, y + self.ROW / 2 - 4, bar_w, 8)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T.RAISED))
            p.drawRoundedRect(track, 4, 4)
            w = max(8.0, bar_w * n / top * self._t)
            fill = QRectF(track.x(), track.y(), w, 8)
            c = T.mix(T.ACCENT, T.ACCENT_2, i / max(1, len(self._items) - 1))
            p.setBrush(c)
            p.drawRoundedRect(fill, 4, 4)
            p.setPen(QColor(T.MUTED))
            p.drawText(QRectF(bar_x + bar_w, y, 36, self.ROW), Qt.AlignVCenter | Qt.AlignRight, str(n))


class Toggle(QAbstractButton):
    """Animated on/off switch."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)
        self._pos = 0.0
        self._a = _anim(self, self._set, 160)
        self.toggled.connect(self._animate)

    def _set(self, v):
        self._pos = float(v)
        self.update()

    def _animate(self, on):
        self._a.stop()
        self._a.setDuration(T.dur(160))
        self._a.setStartValue(self._pos)
        self._a.setEndValue(1.0 if on else 0.0)
        self._a.start()
        if not T.MOTION["enabled"]:
            self._set(1.0 if on else 0.0)

    def setChecked(self, on):
        super().setChecked(on)
        self._set(1.0 if on else 0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(T.ACCENT), 1.5) if self.hasFocus() else Qt.NoPen)
        p.setBrush(T.mix(T.BORDER_HI, T.ACCENT_BTN, self._pos))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        x = 4 + self._pos * (self.width() - 22)
        p.drawEllipse(QRectF(x, 4, 14, 14))


class ScorePicker(QWidget):
    """Segmented 0–10 score selector with a sliding highlight. Keyboard: ←/→, 0–9."""
    valueChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = None
        self._pos = 0.0
        self._hover = -1
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(11 * 34)
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
            if animate and had and T.MOTION["enabled"]:
                self._a.stop()
                self._a.setDuration(T.dur(220))
                self._a.setStartValue(self._pos)
                self._a.setEndValue(float(v))
                self._a.start()
            else:
                self._set(float(v))
        self.update()
        if emit:
            self.valueChanged.emit(v)

    def _cell(self, i):
        w = self.width() / 11
        return QRectF(i * w + 2, 2, w - 4, self.height() - 4)

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
        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(T.ACCENT if self.hasFocus() else T.BORDER), 1))
        p.setBrush(QColor(T.RAISED))
        p.drawRoundedRect(outer, 10, 10)
        if self._hover >= 0:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T.HOVER))
            p.drawRoundedRect(self._cell(self._hover), 8, 8)
        if self._value is not None:
            w = self.width() / 11
            hl = QRectF(self._pos * w + 2, 2, w - 4, self.height() - 4)
            c = QColor(T.score_color(round(self._pos)))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(hl, 8, 8)
        f = QFont(T.FONT)
        f.setPixelSize(14)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        for i in range(11):
            selected = self._value is not None and abs(self._pos - i) < 0.5
            p.setPen(QColor("#0B0D12") if selected else QColor(T.TEXT if i == self._hover else T.MUTED))
            p.drawText(self._cell(i), Qt.AlignCenter, str(i))


class EmptyState(QWidget):
    def __init__(self, icon_name, title, text, action_text=None, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(8)
        badge = IconBadge(icon_name, T.ACCENT, 52)
        lay.addWidget(badge, 0, Qt.AlignHCenter)
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
    """Thin gradient bar that animates to its value (0..1)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._v = 0.0
        self.setFixedHeight(6)
        self._a = _anim(self, self._set, 300)

    def _set(self, v):
        self._v = float(v)
        self.update()

    def set_value(self, v):
        self._a.stop()
        self._a.setDuration(T.dur(300))
        self._a.setStartValue(self._v)
        self._a.setEndValue(float(v))
        self._a.start()
        if not T.MOTION["enabled"]:
            self._set(v)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.RAISED))
        p.drawRoundedRect(QRectF(self.rect()), 3, 3)
        if self._v > 0:
            g = QLinearGradient(0, 0, self.width(), 0)
            g.setColorAt(0, QColor(T.ACCENT))
            g.setColorAt(1, QColor(T.ACCENT_2))
            p.setBrush(g)
            p.drawRoundedRect(QRectF(0, 0, max(6.0, self.width() * self._v), self.height()), 3, 3)


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
        self._a.stop()
        self._a.setDuration(T.dur(320))
        self._a.setStartValue(self._t)
        self._a.setEndValue(1.0 if self._back else 0.0)
        self._a.start()
        if not T.MOTION["enabled"]:
            self._set(1.0 if self._back else 0.0)
        self.flipped.emit(self._back)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.flip()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.flip()
        else:
            super().keyPressEvent(e)

    def _font(self, px, weight=QFont.Normal, italic=False):
        f = QFont(T.FONT)
        f.setPixelSize(px)
        f.setWeight(weight)
        f.setItalic(italic)
        return f

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = min(self.width() - 4, 620)
        r = QRectF((self.width() - w) / 2, 2, w, self.height() - 4)
        sx = abs(math.cos(math.pi * self._t))
        showing_back = self._t > 0.5
        c = r.center()
        p.translate(c)
        p.scale(max(sx, 0.001), 1)
        p.translate(-c)
        p.setPen(QPen(QColor(T.ACCENT if self.hasFocus() else T.BORDER_HI), 1.2))
        p.setBrush(QColor(T.RAISED if showing_back else T.SURFACE))
        p.drawRoundedRect(r, 18, 18)
        if not self._card:
            return
        inner = r.adjusted(28, 22, -28, -22)
        p.setPen(QColor(T.MUTED))
        p.setFont(self._font(11, QFont.DemiBold))
        p.drawText(inner, Qt.AlignTop | Qt.AlignHCenter, "MEANING" if showing_back else "WORD")
        if not showing_back:
            p.setPen(QColor(T.TEXT))
            p.setFont(self._font(34, QFont.DemiBold))
            p.drawText(inner, Qt.AlignCenter | Qt.TextWordWrap, self._card["word"])
            p.setPen(QColor(T.FAINT))
            p.setFont(self._font(12))
            p.drawText(inner, Qt.AlignBottom | Qt.AlignHCenter, "Click or press Space to flip")
            return
        body = inner.adjusted(0, 26, 0, -24)
        meaning = self._card["meaning"] or "(no meaning yet — add one in the word list)"
        blocks = [(meaning, self._font(22, QFont.DemiBold), T.TEXT)]
        if self._card["example"]:
            blocks.append((f"“{self._card['example']}”", self._font(15, italic=True), T.MUTED))
        if self._card["synonyms"]:
            blocks.append(("≈ " + self._card["synonyms"], self._font(13, QFont.Medium), T.ACCENT))
        heights = []
        for text, font, _ in blocks:
            p.setFont(font)
            heights.append(p.boundingRect(body, Qt.AlignHCenter | Qt.TextWordWrap, text).height())
        gap = 14
        y = body.top() + max(0.0, (body.height() - sum(heights) - gap * (len(blocks) - 1)) / 2)
        for (text, font, color), h in zip(blocks, heights):
            p.setFont(font)
            p.setPen(QColor(color))
            p.drawText(QRectF(body.left(), y, body.width(), h), Qt.AlignHCenter | Qt.TextWordWrap, text)
            y += h + gap
        p.setPen(QColor(T.FAINT))
        p.setFont(self._font(12))
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
