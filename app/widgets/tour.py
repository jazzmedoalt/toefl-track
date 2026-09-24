"""Guided tour hosted by "Dot", a little dot-matrix face. A dimmed, dotted scrim with a springy
spotlight on the thing being explained, a step card (STEP n OF 10), and confetti at the end."""
import math
import random

from PySide6.QtCore import (QEasingCurve, QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation,
                            QRect, QRectF, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QShortcut
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget)

from .. import db
from .. import theme as T
from .cards import Card, ScorePicker, button, label

# 7×7 dot-matrix faces: '#' lit, 'r' red, '.' off
FACES = {
    "happy": [".......", ".#...#.", ".#...#.", ".......", "#.....#", ".#####.", "......."],
    "blink": [".......", ".......", "##...##", ".......", "#.....#", ".#####.", "......."],
    "wink":  [".......", ".#.....", ".#..###", ".......", "#.....#", ".#####.", "......."],
    "wow":   [".......", ".#...#.", ".#...#.", ".......", "...#...", "..#.#..", "...#..."],
    "cool":  ["#######", "###.###", ".......", ".......", "......#", ".#####.", "......."],
    "think": ["......r", ".#...#.", ".#...#.", ".......", ".......", "..####.", "......."],
    "love":  [".......", "rr...rr", "rr...rr", ".......", "#.....#", ".#####.", "......."],
    "party": ["r.....r", ".#...#.", ".#...#.", ".......", ".#####.", ".#...#.", "..###.."],
}


class Face(QWidget):
    """Dot the mascot: blinks, bounces on every new step, glances toward the spotlight."""

    def __init__(self, size=56, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._face = "happy"
        self._blink = False
        self._look = 0          # -1 left, 0 center, 1 right
        self._squash = 0.0
        self._bounce = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=520)
        self._bounce.valueChanged.connect(self._tick)
        self._blinker = QTimer(self, interval=3100, timeout=self._do_blink)
        if T.MOTION["enabled"]:
            self._blinker.start()

    def set_face(self, face, look=0):
        self._face, self._look = face, look
        if T.MOTION["enabled"]:
            self._bounce.stop()
            self._bounce.start()
        self.update()

    def _tick(self, v):
        self._squash = float(v)
        self.update()

    def _do_blink(self):
        if self._face in ("happy", "wow", "think", "party"):
            self._blink = True
            self.update()
            QTimer.singleShot(140, self._unblink)

    def _unblink(self):
        self._blink = False
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        p.setPen(QColor(T.BORDER_HI))
        p.setBrush(QColor(T.SURFACE))
        p.drawEllipse(QRectF(0.5, 0.5, s - 1, s - 1))
        # squash-and-stretch bounce: up then settle
        t = self._squash
        hop = math.sin(t * math.pi) * (1 - t) * 7
        sx = 1 + 0.12 * math.sin(t * math.pi * 2) * (1 - t)
        p.translate(s / 2, s / 2 - hop)
        p.scale(sx, 2 - sx)
        grid = FACES["blink" if self._blink else self._face]
        pitch = s / 8.6
        r = pitch * 0.40
        for y, row in enumerate(grid):
            if y in (1, 2) and self._look:
                row = (row[-1] + row[:-1]) if self._look > 0 else (row[1:] + row[0])
            for x, ch in enumerate(row):
                c = QColor(T.TEXT if ch == "#" else T.RED if ch == "r" else T.FAINT)
                if ch == ".":
                    c.setAlphaF(0.35)
                p.setPen(Qt.NoPen)
                p.setBrush(c)
                rr = r if ch != "." else r * 0.45
                p.drawEllipse(QPointF((x - 3) * pitch, (y - 3) * pitch), rr, rr)


class StepDots(QWidget):
    """n dots: done = lit, current = red and pulsing, upcoming = faint."""

    def __init__(self, n, parent=None):
        super().__init__(parent)
        self.n, self.i, self._pulse = n, 0, 0.0
        self.setFixedHeight(14)
        self.setMinimumWidth(n * 14)
        self._a = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=1200, loopCount=-1)
        self._a.valueChanged.connect(self._tick)
        if T.MOTION["enabled"]:
            self._a.start()

    def _tick(self, v):
        self._pulse = float(v)
        self.update()

    def set_index(self, i):
        self.i = i
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        for k in range(self.n):
            c = QPointF(7 + k * 14, 7)
            if k == self.i:
                glow = QColor(T.RED)
                glow.setAlphaF(0.25 * (1 - self._pulse))
                p.setBrush(glow)
                p.drawEllipse(c, 3.5 + 3.5 * self._pulse, 3.5 + 3.5 * self._pulse)
                p.setBrush(QColor(T.RED))
                p.drawEllipse(c, 3.5, 3.5)
            else:
                p.setBrush(QColor(T.TEXT if k < self.i else T.FAINT))
                p.drawEllipse(c, 2.6, 2.6)


def _steps(win):
    """Each step: page to open, candidate target widgets (first visible ones win), words, face."""
    d, s, f = win.dashboard, win.sets, win.flashcards

    def demo_score():
        pick = ScorePicker()
        pick.setAttribute(Qt.WA_TransparentForMouseEvents)
        pick.setFocusPolicy(Qt.NoFocus)
        seq = iter([3, 6, 9, 7] * 50)
        timer = QTimer(pick, interval=900, timeout=lambda: pick.setValue(next(seq), animate=T.MOTION["enabled"]))
        pick.setValue(7, animate=False)
        timer.start()
        return pick

    return [
        dict(page=None, targets=lambda: [], face="happy", title="Hi, I'm Dot!",
             text="I'll show you around in 11 quick steps. Takes a minute, promise."),
        dict(page=win.DASH, targets=lambda: [win.sidebar], face="wink", title="The menu",
             text="Everything lives here. Click a word to jump there."),
        dict(page=win.SETS, targets=lambda: [s.list.new_name, s.list.add_btn], face="think",
             title="1. Make a set",
             text="A set is a folder. Name it after your book or test, like “Set 1 · Reading”."),
        dict(page=win.SETS, targets=lambda: [s.list.grid_host], face="happy", title="2. Add practices",
             text="Open a set and add a practice for every test you do. One test = one practice."),
        dict(page=win.SETS, targets=lambda: [], face="wow", title="3. Score + mistakes", demo=demo_score,
             text="Pick how many you got right out of 10. Then write each wrong answer, the right one, "
                  "and what kind of mistake it was. Press Enter to save it."),
        dict(page=win.DASH, targets=lambda: [d.c_streak, d.c_practices, d.c_avg, d.c_due, d.empty],
             face="cool", title="Your numbers",
             text="Streak, average and progress update on their own. No maths needed."),
        dict(page=win.CALENDAR, targets=lambda: [win.calendar.month], face="think", title="Your calendar",
             text="Red day = rough day. White day = great day. Click a day to see what you did."
             if T.MODE == "dark" else
             "Red day = rough day. Black day = great day. Click a day to see what you did."),
        dict(page=win.MISTAKES, targets=lambda: [win.mistakes.reason], face="think", title="Find your breakpoint",
             text="Tag each mistake with why it fooled you: sound-alike, false cognate… Breakpoints then "
                  "shows the trap you fall into most, and how to beat it."),
        dict(page=win.FLASHCARDS, targets=lambda: [f.list.paste_btn], face="love", title="Learn the words",
             text="Add cards one by one, from a mistake, or paste word:meaning lines. "
                  "Stuck? Copy the AI prompt and let it do the typing."),
        dict(page=win.QUIZ, targets=lambda: [win.quiz.setup.card, win.quiz.setup.empty], face="wow",
             title="Quiz yourself", text="It asks you your old mistakes until they stick. Sneaky, but it works."),
        dict(page=win.SETTINGS, targets=lambda: [win.settings.appearance], face="party", title="Make it yours",
             text="Dark or light, exam date, and backups live here. That's it — you're ready!"),
    ]


class Tour(QWidget):
    closed = Signal()
    PAD = 8
    CARD_W = 360

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.steps = _steps(win)
        self.i = -1
        self._spot = None           # QRectF or None (current, animated)
        self._phase = 0.0
        self._confetti = []
        self._closing = False
        self.setGeometry(win.rect())
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName("Guided tour")
        win.installEventFilter(self)

        self._spot_anim = QVariantAnimation(self, duration=T.dur(380), easingCurve=QEasingCurve.OutBack)
        self._spot_anim.valueChanged.connect(self._set_spot)
        self._march = QTimer(self, interval=60, timeout=self._advance_march)
        self._fx_timer = QTimer(self, interval=16, timeout=self._step_confetti)

        # ---- the step card
        self.card = Card(self, padding=18)
        self.card.setFixedWidth(self.CARD_W)
        cl = self.card.layout()
        cl.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(12)
        self.face = Face(56)
        head.addWidget(self.face, 0, Qt.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.count = label("", "eyebrow")
        self.title = label("", "h2")
        self.title.setWordWrap(True)
        titles.addWidget(self.count)
        titles.addWidget(self.title)
        head.addLayout(titles, 1)
        cl.addLayout(head)
        self.text = label("")
        self.text.setWordWrap(True)
        cl.addWidget(self.text)
        self.demo_host = QVBoxLayout()
        cl.addLayout(self.demo_host)
        self.dots = StepDots(len(self.steps))
        cl.addWidget(self.dots)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.skip = button("Skip tour", "ghost")
        self.back = button("Back", "ghost", "chevron-left")
        self.next = button("Next", "primary", "chevron-right")
        self.next.setLayoutDirection(Qt.RightToLeft)     # arrow after the word
        row.addWidget(self.skip)
        row.addStretch(1)
        row.addWidget(self.back)
        row.addWidget(self.next)
        cl.addLayout(row)
        self.skip.clicked.connect(lambda: self.close_tour(True, "Tour skipped — press ? anytime"))
        self.back.clicked.connect(lambda: self.go(self.i - 1))
        self.next.clicked.connect(self._next)
        self._card_fx = QGraphicsOpacityEffect(self.card)
        self._card_fx.setOpacity(0)
        self.card.setGraphicsEffect(self._card_fx)
        self._card_group = None
        self.card.installEventFilter(self)      # refit the card whenever its content changes

        for keys, fn in ((Qt.Key_Right, self._next), (Qt.Key_Return, self._next), (Qt.Key_Enter, self._next),
                         (Qt.Key_Left, lambda: self.go(self.i - 1)),
                         (Qt.Key_Escape, lambda: self.close_tour(True, "Tour skipped — press ? anytime"))):
            sc = QShortcut(QKeySequence(keys), self, fn)
            sc.setContext(Qt.WidgetWithChildrenShortcut)

    # ---- lifecycle
    def start(self):
        self.show()
        self.raise_()
        self.setFocus()
        if T.MOTION["enabled"]:
            self._march.start()
        self.go(0)

    def close_tour(self, mark_done=True, message=None):
        if self._closing:
            return
        self._closing = True
        if mark_done:
            db.set_setting("tour_done", "1")
        self.win.removeEventFilter(self)
        self.hide()
        self.deleteLater()
        self.closed.emit()
        if mark_done:
            self.win.go_page(self.win.DASH)
        if message:
            self.win.toast(message, 2200)

    def _next(self):
        if self.i >= len(self.steps) - 1:
            self._finish()
        else:
            self.go(self.i + 1)

    def _finish(self):
        if not T.MOTION["enabled"]:
            self.close_tour(True, "Tour finished — press ? anytime")
            return
        self.next.setEnabled(False)
        self.face.set_face("party")
        c = self.card.geometry().center()
        cols = (T.RED, T.TEXT, T.MUTED, T.RED)
        self._confetti = [[c.x(), c.y() - 40, random.uniform(-7, 7), random.uniform(-13, -5),
                           random.choice(cols), random.uniform(2, 4.5)] for _ in range(70)]
        self._fx_timer.start()
        QTimer.singleShot(1300, lambda: self.close_tour(True, "Tour finished — press ? anytime"))

    # ---- steps
    def go(self, i):
        if not 0 <= i < len(self.steps) or self._closing:
            return
        self.i = i
        st = self.steps[i]
        page_change = st["page"] is not None and self.win.pages.currentIndex() != st["page"]
        if st["page"] == self.win.SETS:
            self.win.sets.show_list()
        if st["page"] == self.win.FLASHCARDS:
            self.win.flashcards.show_list()
        if page_change:
            self.win.go_page(st["page"])
        self._fade_card(0.0, 110)
        # let the page slide finish before measuring the target
        QTimer.singleShot(T.dur(340) if page_change else T.dur(120), lambda i=i: self._settle(i))

    def _target_rect(self, st):
        ws = [w for w in st["targets"]() if w is not None and w.isVisible()]
        if not ws:
            return None
        for w in ws[:1]:
            par = w.parentWidget()
            while par is not None and not isinstance(par, QScrollArea):
                par = par.parentWidget()
            if par is not None:
                par.ensureWidgetVisible(w, 0, 60)
        rect = QRect()
        for w in ws:
            rect = rect.united(QRect(w.mapTo(self.win, QPoint(0, 0)), w.size()))
        rect = rect.intersected(self.win.rect().adjusted(8, 44, -8, -8))
        return QRectF(rect).adjusted(-self.PAD, -self.PAD, self.PAD, self.PAD) if not rect.isEmpty() else None

    def _settle(self, i):
        if i != self.i or self._closing:
            return
        st = self.steps[i]
        target = self._target_rect(st)
        # card content
        n = len(self.steps)
        self.count.setText(f"STEP {i + 1} OF {n}")
        self.title.setText(st["title"])
        self.text.setText(st["text"])
        while self.demo_host.count():
            w = self.demo_host.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.card.setFixedWidth(self.CARD_W + (80 if st.get("demo") else 0))   # the demo picker needs room
        if st.get("demo"):
            self.demo_host.addWidget(st["demo"]())
        self.dots.set_index(i)
        self.back.setVisible(i > 0)
        self.next.setText("Let's go!" if i == n - 1 else "Next")
        self.next.setEnabled(True)
        self.card.adjustSize()
        # spotlight
        start = self._spot if self._spot is not None else (
            QRectF(target.center(), target.center()) if target is not None else None)
        self._spot_anim.stop()
        if target is not None and start is not None and T.MOTION["enabled"]:
            self._spot_anim.setStartValue(start)
            self._spot_anim.setEndValue(target)
            self._spot_anim.start()
        else:
            self._set_spot(target)
        # card placement + mascot glance
        pos, look = self._place(target)
        self.face.set_face(st["face"], look)
        self._show_card(pos)
        self.next.setFocus()

    def _place(self, target):
        W, H = self.width(), self.height()
        lay = self.card.layout()
        lay.activate()
        cw = self.card.width()
        ch = lay.totalHeightForWidth(cw) if lay.hasHeightForWidth() else self.card.sizeHint().height()
        self.card.resize(cw, ch)
        m = 16
        if target is None:
            return QPoint(int((W - cw) / 2), int((H - ch) / 2)), 0
        y = int(min(max(target.center().y() - ch / 2, 44), H - ch - m))
        if target.right() + 20 + cw < W - m:
            return QPoint(int(target.right() + 20), y), -1           # card on the right, Dot looks left
        if target.left() - 20 - cw > m:
            return QPoint(int(target.left() - 20 - cw), y), 1
        x = int(min(max(target.center().x() - cw / 2, m), W - cw - m))
        if target.bottom() + 16 + ch < H - m:
            return QPoint(x, int(target.bottom() + 16)), 0
        if target.top() - 16 - ch > 44:
            return QPoint(x, int(target.top() - 16 - ch)), 0
        return QPoint(int((W - cw) / 2), int((H - ch) / 2)), 0

    def _show_card(self, pos):
        if self._card_group:
            self._card_group.stop()
        self.card.raise_()
        if not T.MOTION["enabled"]:
            self.card.move(pos)
            self._card_fx.setOpacity(1.0)
            return
        slide = QPropertyAnimation(self.card, b"pos")
        slide.setStartValue(pos + QPoint(0, 14))
        slide.setEndValue(pos)
        slide.setDuration(260)
        slide.setEasingCurve(QEasingCurve.OutCubic)
        fade = QPropertyAnimation(self._card_fx, b"opacity")
        fade.setStartValue(self._card_fx.opacity())
        fade.setEndValue(1.0)
        fade.setDuration(220)
        fade.setEasingCurve(QEasingCurve.OutCubic)
        self._card_group = QParallelAnimationGroup(self)
        self._card_group.addAnimation(slide)
        self._card_group.addAnimation(fade)
        self._card_group.start()

    def _fade_card(self, to, ms):
        if self._card_group:
            self._card_group.stop()
        if not T.MOTION["enabled"] or self._card_fx.opacity() == to:
            self._card_fx.setOpacity(to)
            return
        fade = QPropertyAnimation(self._card_fx, b"opacity", self)
        fade.setStartValue(self._card_fx.opacity())
        fade.setEndValue(to)
        fade.setDuration(ms)
        fade.setEasingCurve(QEasingCurve.InCubic)
        self._card_group = QParallelAnimationGroup(self)
        self._card_group.addAnimation(fade)
        self._card_group.start()

    # ---- animation ticks
    def _set_spot(self, r):
        self._spot = QRectF(r) if r is not None else None
        self.update()

    def _advance_march(self):
        self._phase = (self._phase + 0.004) % 1.0
        self.update()

    def _step_confetti(self):
        alive = []
        for c in self._confetti:
            c[0] += c[2]
            c[1] += c[3]
            c[3] += 0.55            # gravity
            c[2] *= 0.985
            if c[1] < self.height() + 10:
                alive.append(c)
        self._confetti = alive
        self.update()

    # ---- events
    def _fit_card(self):
        lay = self.card.layout()
        h = lay.totalHeightForWidth(self.card.width()) if lay.hasHeightForWidth() else lay.sizeHint().height()
        if h != self.card.height():
            self.card.resize(self.card.width(), h)
            bottom = self.height() - 16
            if self.card.geometry().bottom() > bottom:
                self.card.move(self.card.x(), max(44, bottom - h))

    def eventFilter(self, obj, e):
        if obj is self.card and e.type() == e.Type.LayoutRequest:
            QTimer.singleShot(0, self._fit_card)
            return False
        if obj is self.win and e.type() == e.Type.Resize:
            self.setGeometry(self.win.rect())
            if 0 <= self.i < len(self.steps):
                QTimer.singleShot(0, lambda: self._settle(self.i))
        return False

    def mousePressEvent(self, e):
        e.accept()                  # the scrim swallows clicks; only the card acts

    def mouseReleaseEvent(self, e):
        e.accept()

    def wheelEvent(self, e):
        e.accept()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scrim = QPainterPath()
        scrim.addRect(QRectF(self.rect()))
        if self._spot is not None:
            hole = QPainterPath()
            hole.addRoundedRect(self._spot, 16, 16)
            scrim = scrim.subtracted(hole)
        dim = QColor(T.BG)
        dim.setAlphaF(0.84)
        p.fillPath(scrim, dim)
        # the scrim's own dot grid
        p.save()
        p.setClipPath(scrim)
        dot = QColor(T.TEXT)
        dot.setAlphaF(0.10)
        p.setPen(Qt.NoPen)
        p.setBrush(dot)
        for y in range(9, self.height(), 18):
            for x in range(9, self.width(), 18):
                p.drawEllipse(QPointF(x, y), 1, 1)
        p.restore()
        # marching red dots around the spotlight
        if self._spot is not None and self._spot.width() > 4:
            ring = QPainterPath()
            ring.addRoundedRect(self._spot.adjusted(-3, -3, 3, 3), 18, 18)
            n = max(16, int(ring.length() / 9))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(T.RED))
            for k in range(n):
                p.drawEllipse(ring.pointAtPercent((k / n + self._phase) % 1.0), 1.7, 1.7)
        for x, y, _, _, color, r in self._confetti:
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(x, y), r, r)
