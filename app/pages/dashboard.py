from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from .. import db
from .. import theme as T
from ..widgets.cards import (Card, CategoryBars, EmptyState, IconBadge, ProgressBar, ScorePill,
                             ScoreRing, StatCard, button, label)
from ..widgets.chart import ActivityHeatmap, TrendChart
from .base import Page, clear_layout


def _card_title(card, title, caption=""):
    card.layout().addWidget(label(title, "h2"))
    if caption:
        card.layout().addWidget(label(caption, "caption"))


class DashboardPage(Page):
    def __init__(self, win):
        super().__init__(win, "Dashboard", "Your TOEFL progress at a glance")
        self.set_exam = self.add_action(button("Set exam date", "ghost", "calendar-days"))
        self.set_exam.clicked.connect(lambda: win.go_page(win.SETTINGS))
        self.stack = QStackedWidget()
        self.body.addWidget(self.stack, 1)

        self.empty = EmptyState("graduation-cap", "Start tracking your practice",
                                "Create a set, add a practice, then log your score and the "
                                "answers you got wrong.", "Create your first set")
        self.empty.action.clicked.connect(lambda: win.go_sets(focus_new=True))
        self.stack.addWidget(self.empty)

        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)
        self.stack.addWidget(content)

        # exam banner
        self.exam = Card(padding=14)
        el = QHBoxLayout()
        el.setSpacing(14)
        el.addWidget(IconBadge("calendar-days", T.ACCENT_2, 40))
        et = QVBoxLayout()
        et.setSpacing(2)
        self.exam_title = label("", "h2")
        self.exam_sub = label("", "caption")
        et.addWidget(self.exam_title)
        et.addWidget(self.exam_sub)
        el.addLayout(et, 1)
        pv = QVBoxLayout()
        pv.setSpacing(6)
        self.exam_status = label("")
        self.exam_status.setAlignment(Qt.AlignRight)
        self.exam_bar = ProgressBar()
        self.exam_bar.setFixedWidth(220)
        pv.addWidget(self.exam_status)
        pv.addWidget(self.exam_bar)
        el.addLayout(pv)
        self.exam.layout().addLayout(el)
        col.addWidget(self.exam)

        grid = QGridLayout()
        grid.setSpacing(14)
        self.c_streak = StatCard("Streak", "flame", T.WARN)
        self.c_practices = StatCard("Practices", "file-text", T.ACCENT)
        self.c_avg = StatCard("Average", "target", T.ACCENT_2)
        self.c_due = StatCard("Cards due", "sparkles", T.GOOD, clickable=True)
        self.c_due.setToolTip("Open flashcards")
        self.c_due.clicked.connect(lambda: win.go_page(win.FLASHCARDS))
        for i, c in enumerate((self.c_streak, self.c_practices, self.c_avg, self.c_due)):
            grid.addWidget(c, 0, i)
        col.addLayout(grid)

        row = QHBoxLayout()
        row.setSpacing(14)
        trend = Card()
        _card_title(trend, "Score trend", "Every scored practice, oldest to latest. Hover for details.")
        self.chart = TrendChart()
        trend.layout().addWidget(self.chart, 1)
        row.addWidget(trend, 2)
        ring_card = Card()
        _card_title(ring_card, "Overall")
        self.ring = ScoreRing()
        ring_card.layout().addWidget(self.ring, 1)
        self.ring_note = label("", "muted")
        self.ring_note.setAlignment(Qt.AlignCenter)
        ring_card.layout().addWidget(self.ring_note)
        row.addWidget(ring_card, 1)
        col.addLayout(row, 1)

        row2 = QHBoxLayout()
        row2.setSpacing(14)
        act = Card()
        _card_title(act, "Activity", "Practices, card reviews and quiz answers. Hover a day.")
        self.heatmap = ActivityHeatmap()
        act.layout().addWidget(self.heatmap)
        act.layout().addStretch(1)
        row2.addWidget(act, 1)
        cats = Card()
        _card_title(cats, "Top mistake types")
        self.cats_caption = label("", "caption")
        cats.layout().addWidget(self.cats_caption)
        self.bars = CategoryBars()
        cats.layout().addWidget(self.bars)
        self.no_cats = label("No mistakes logged yet.", "muted")
        cats.layout().addWidget(self.no_cats)
        cats.layout().addStretch(1)
        row2.addWidget(cats, 1)
        col.addLayout(row2)
        recent = Card()
        _card_title(recent, "Recent practices")
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(6)
        recent.layout().addLayout(self.recent_list)
        col.addWidget(recent)

    def refresh(self):
        s = db.stats()
        exam = db.exam()
        self.set_exam.setVisible(exam is None)
        if s["sets"] == 0 and s["cards"] == 0:
            self.stack.setCurrentIndex(0)
            self.subtitle.setText("Your TOEFL progress at a glance")
            return
        self.stack.setCurrentIndex(1)
        self.subtitle.setText(date.today().strftime("%A, %d %B") + " · keep logging, every mistake counts")
        scored = len(s["series"])
        self._show_exam(exam)
        st = s["streak"]
        self.c_streak.set_value(st, "{:.0f}", "day in a row" if st == 1 else "days in a row" if st
                                else "study today to start one")
        self.c_practices.set_value(s["practices"], sub=f"across {s['sets']} set{'s' * (s['sets'] != 1)}")
        self.c_avg.set_value(s["avg"], "{:.1f}", "out of 10")
        self.c_due.set_value(s["due"], sub=f"of {s['cards']} flashcards" if s["cards"] else "add words to review")
        per = f" · {s['mistakes'] / scored:.1f} per practice" if scored else ""
        self.cats_caption.setText(f"{s['mistakes']} logged{per}")
        self.heatmap.set_days(db.activity_days())
        self.chart.set_points(s["series"])
        self.ring.set_value(s["avg"])
        if s["avg"] is None:
            self.ring_note.setText("Score a practice to see this")
        else:
            last = s["series"][-5:]
            recent_avg = sum(d["score"] for d in last) / len(last)
            delta = recent_avg - s["avg"]
            trend = "on the rise ↑" if delta > 0.2 else "slipping ↓" if delta < -0.2 else "steady"
            self.ring_note.setText(f"{T.score_label(round(s['avg']))} · best {s['best']}/10\n"
                                   f"last 5: {recent_avg:.1f} ({trend})")

        items = [(r["category"], r["n"]) for r in s["top"]]
        self.bars.setVisible(bool(items))
        self.no_cats.setVisible(not items)
        self.bars.set_items(items)

        clear_layout(self.recent_list)
        for r in s["recent"]:
            self.recent_list.addWidget(self._recent_row(r))

    def _show_exam(self, e):
        self.exam.setVisible(e is not None)
        if not e:
            return
        d = e["days_left"]
        self.exam_title.setText(f"{d} day{'s' * (d != 1)} to your TOEFL" if d > 0 else
                                "Exam day is today. Good luck!" if d == 0 else
                                f"Your exam was {-d} day{'s' * (d != -1)} ago")
        target, avg = e["target"], e["recent_avg"]
        if avg is None:
            self.exam_sub.setText(f"Target average {target}/10 · score a practice to track progress")
            self.exam_status.setText("")
            self.exam_bar.set_value(0)
            return
        self.exam_sub.setText(f"Target average {target}/10 · your last 5 practices: {avg:.1f}")
        if e["gap"] <= 0:
            self.exam_status.setText("On track ✓")
            self.exam_status.setStyleSheet(f"color: {T.GOOD}; font-weight: 600;")
        else:
            self.exam_status.setText(f"{e['gap']:.1f} to go")
            self.exam_status.setStyleSheet(f"color: {T.WARN}; font-weight: 600;")
        self.exam_bar.set_value(min(1.0, avg / target) if target else 1.0)

    def _recent_row(self, r):
        c = Card(clickable=True, radius=10, padding=10)
        c.setAccessibleName(f"Open {r['set_name']} {r['name']}")
        lay = QHBoxLayout()
        lay.setSpacing(10)
        txt = QVBoxLayout()
        txt.setSpacing(0)
        txt.addWidget(label(f"{r['set_name']} · {r['name']}"))
        m = r["mistakes"]
        txt.addWidget(label(f"{r['date']} · {m} mistake{'s' * (m != 1)}", "caption"))
        lay.addLayout(txt, 1)
        lay.addWidget(ScorePill(r["score"]))
        c.layout().addLayout(lay)
        c.clicked.connect(lambda pid=r["id"]: self.win.open_practice(pid))
        return c
