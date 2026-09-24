"""Score calendar: Month grid or Week columns, each day colored by its average score."""
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from .. import db
from .. import theme as T
from ..widgets.calendar import MonthGrid, WeekView
from ..widgets.cards import Card, ScorePill, button, label
from ..widgets.toast import AnimatedStack
from .base import Page, clear_layout


def _seg(text):
    b = QPushButton(text)
    b.setCheckable(True)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton {{ border: none; border-radius: 14px; padding: 5px 16px; min-height: 18px; color: {T.MUTED};"
        f" font-family: \"{T.MONO}\"; font-size: 12px; letter-spacing: 1px; }}"
        f"QPushButton:hover {{ color: {T.TEXT}; }}"
        f"QPushButton:checked {{ background: {T.TEXT}; color: #000000; }}")
    return b


class CalendarPage(Page):
    MONTH, WEEK = 0, 1

    def __init__(self, win):
        super().__init__(win, "Calendar", "Every day colored by how you scored.", scroll=True)
        self.mode = self.MONTH
        self.anchor = date.today()      # any date inside the shown month/week
        self.selected = date.today()

        # view toggle
        seg = QWidget()
        seg.setStyleSheet(f"QWidget#Seg {{ border: 1px solid {T.BORDER_HI}; border-radius: 17px; }}")
        seg.setObjectName("Seg")
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.setSpacing(2)
        self.grp = QButtonGroup(self)
        for i, t in enumerate(("MONTH", "WEEK")):
            b = _seg(t)
            self.grp.addButton(b, i)
            sl.addWidget(b)
        self.grp.button(0).setChecked(True)
        self.grp.idClicked.connect(self._set_mode)
        self.add_action(seg)

        # navigation row: ‹ title ›  ...  legend  Today
        nav = QHBoxLayout()
        nav.setSpacing(6)
        self.prev = button("", "ghost", "chevron-left")
        self.prev.setToolTip("Previous")
        self.next = button("", "ghost", "chevron-right")
        self.next.setToolTip("Next")
        self.prev.clicked.connect(lambda: self._step(-1))
        self.next.clicked.connect(lambda: self._step(1))
        self.range_title = label("", "display-sm")
        nav.addWidget(self.prev)
        nav.addWidget(self.range_title)
        nav.addWidget(self.next)
        nav.addStretch(1)
        for color, text in ((T.RED, "< 5"), (T.MID, "5–7"), (T.TEXT, "8–10")):
            dot = label("●")
            dot.setStyleSheet(f"color: {color}; font-size: 12px;")
            nav.addWidget(dot)
            nav.addWidget(label(text, "eyebrow"))
            nav.addSpacing(6)
        today = button("Today", "ghost")
        today.clicked.connect(self._today)
        nav.addWidget(today)
        self.body.addLayout(nav)

        # views
        self.month = MonthGrid()
        self.month.daySelected.connect(self._pick_day)
        self.week = WeekView()
        self.week.practiceClicked.connect(self.win.open_practice)
        self.views = AnimatedStack()
        self.views.addWidget(self.month)
        self.views.addWidget(self.week)
        self.views.setMinimumHeight(420)
        self.body.addWidget(self.views)

        # selected day (month view)
        self.day_card = Card()
        dl = self.day_card.layout()
        self.day_title = label("", "h2")
        self.day_sub = label("", "eyebrow")
        head = QHBoxLayout()
        head.addWidget(self.day_title)
        head.addStretch(1)
        head.addWidget(self.day_sub)
        dl.addLayout(head)
        self.day_list = QVBoxLayout()
        self.day_list.setSpacing(2)
        dl.addLayout(self.day_list)
        self.body.addWidget(self.day_card)
        self.body.addStretch(1)

    # ---- range helpers
    def _range(self):
        if self.mode == self.WEEK:
            start = self.anchor - timedelta(days=self.anchor.weekday())
            return start, start + timedelta(days=6)
        first = self.anchor.replace(day=1)
        start = first - timedelta(days=first.weekday())
        return start, start + timedelta(days=41)

    def _title(self):
        if self.mode == self.MONTH:
            return self.anchor.strftime("%B %Y").upper()
        s, e = self._range()
        if s.month == e.month:
            return f"{s.day}–{e.day} {e.strftime('%b %Y')}".upper()
        return f"{s.strftime('%d %b')} – {e.strftime('%d %b')}".upper()

    # ---- actions
    def _set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        self.anchor = self.selected
        self.refresh()
        self.views.slide_to(mode, 1 if mode == self.WEEK else -1)

    def _step(self, d):
        if self.mode == self.WEEK:
            self.anchor += timedelta(days=7 * d)
        else:
            y, m = self.anchor.year, self.anchor.month + d
            y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
            self.anchor = date(y, m, 1)
        self.refresh()

    def _today(self):
        self.anchor = self.selected = date.today()
        self.refresh()

    def _pick_day(self, d):
        self.selected = d
        if (d.year, d.month) != (self.anchor.year, self.anchor.month):
            self.anchor = d
            self.refresh()
        else:
            self._fill_day()

    def refresh(self):
        start, end = self._range()
        self.data = db.scores_by_day(start, end)
        self.range_title.setText(self._title())
        if self.mode == self.MONTH:
            self.month.set_month(self.anchor.year, self.anchor.month, self.data, self.selected)
        else:
            self.week.set_week(start, self.data)
        self.day_card.setVisible(self.mode == self.MONTH)
        self._fill_day()

    def _fill_day(self):
        clear_layout(self.day_list)
        d = self.selected
        items = db.scores_by_day(d, d).get(d.isoformat(), [])
        self.day_title.setText(d.strftime("%A %d %B"))
        avg = db.day_average(items)
        self.day_sub.setText(f"AVG {avg:.1f} / 10" if avg is not None else
                             ("NO SCORE" if items else "NO PRACTICE"))
        if not items:
            self.day_list.addWidget(label("Nothing practiced this day.", "muted"))
            return
        for it in items:
            row = QPushButton()
            row.setCursor(Qt.PointingHandCursor)
            row.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 12px; min-height: 40px; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {T.RAISED}; }}"
                f"QPushButton:focus {{ border: 1px solid {T.TEXT}; }}")
            row.setAccessibleName(f"Open {it['set_name']} {it['name']}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 0, 10, 0)
            rl.addWidget(label(it["name"]))
            rl.addWidget(label(it["set_name"], "caption"))
            rl.addStretch(1)
            pill = ScorePill(it["score"])
            pill.setAttribute(Qt.WA_TransparentForMouseEvents)
            rl.addWidget(pill)
            row.clicked.connect(lambda _=False, pid=it["id"]: self.win.open_practice(pid))
            self.day_list.addWidget(row)
