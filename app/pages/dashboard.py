from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from .. import db
from .. import theme as T
from ..widgets.cards import (Card, CategoryBars, EmptyState, ScorePill, ScoreRing, StatCard,
                             label)
from ..widgets.chart import TrendChart
from .base import Page, clear_layout


def _card_title(card, title, caption=""):
    card.layout().addWidget(label(title, "h2"))
    if caption:
        card.layout().addWidget(label(caption, "caption"))


class DashboardPage(Page):
    def __init__(self, win):
        super().__init__(win, "Dashboard", "Your TOEFL progress at a glance")
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

        grid = QGridLayout()
        grid.setSpacing(14)
        self.c_practices = StatCard("Practices", "file-text", T.ACCENT)
        self.c_avg = StatCard("Average", "target", T.ACCENT_2)
        self.c_best = StatCard("Best score", "trophy", T.GOOD)
        self.c_mistakes = StatCard("Mistakes logged", "book-x", T.DANGER)
        for i, c in enumerate((self.c_practices, self.c_avg, self.c_best, self.c_mistakes)):
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
        cats = Card()
        _card_title(cats, "Top mistake types", "Where your points are going")
        self.bars = CategoryBars()
        cats.layout().addWidget(self.bars)
        self.no_cats = label("No mistakes logged yet.", "muted")
        cats.layout().addWidget(self.no_cats)
        cats.layout().addStretch(1)
        row2.addWidget(cats, 1)
        recent = Card()
        _card_title(recent, "Recent practices")
        self.recent_list = QVBoxLayout()
        self.recent_list.setSpacing(6)
        recent.layout().addLayout(self.recent_list)
        recent.layout().addStretch(1)
        row2.addWidget(recent, 1)
        col.addLayout(row2)

    def refresh(self):
        s = db.stats()
        if s["sets"] == 0:
            self.stack.setCurrentIndex(0)
            self.subtitle.setText("Your TOEFL progress at a glance")
            return
        self.stack.setCurrentIndex(1)
        self.subtitle.setText(date.today().strftime("%A, %d %B") + " · keep logging, every mistake counts")
        scored = len(s["series"])
        self.c_practices.set_value(s["practices"], sub=f"across {s['sets']} set{'s' * (s['sets'] != 1)}")
        self.c_avg.set_value(s["avg"], "{:.1f}", "out of 10")
        self.c_best.set_value(s["best"], "{:.0f}/10", "highest score")
        per = f"{s['mistakes'] / scored:.1f} per practice" if scored else ""
        self.c_mistakes.set_value(s["mistakes"], sub=per)
        self.chart.set_points(s["series"])
        self.ring.set_value(s["avg"])
        if s["avg"] is None:
            self.ring_note.setText("Score a practice to see this")
        else:
            last = s["series"][-5:]
            recent_avg = sum(d["score"] for d in last) / len(last)
            delta = recent_avg - s["avg"]
            trend = "on the rise ↑" if delta > 0.2 else "slipping ↓" if delta < -0.2 else "steady"
            self.ring_note.setText(f"{T.score_label(round(s['avg']))} · last 5: {recent_avg:.1f} ({trend})")

        items = [(r["category"], r["n"]) for r in s["top"]]
        self.bars.setVisible(bool(items))
        self.no_cats.setVisible(not items)
        self.bars.set_items(items)

        clear_layout(self.recent_list)
        for r in s["recent"]:
            self.recent_list.addWidget(self._recent_row(r))

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
