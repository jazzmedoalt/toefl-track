"""Breakpoints: which wrong-answer reason catches you most, whether it's getting better, where it
shows up, and one click to drill it."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import db
from .. import theme as T
from ..widgets.breakpoint_charts import ReasonBars, ReasonMatrix, ReasonTimeline
from ..widgets.cards import Card, EmptyState, button, label
from .base import Page, clear_layout


def _trend(r):
    if r["recent"] > r["prev"]:
        return "↑ GETTING WORSE", T.RED_TEXT
    if r["recent"] < r["prev"]:
        return "↓ IMPROVING", T.TEXT
    return "— STEADY", T.MUTED


class BreakpointsPage(Page):
    def __init__(self, win):
        super().__init__(win, "Breakpoints", "Which trap catches you, and what to do about it")
        self.sel = None
        self.stats = None

        self.empty = EmptyState("crosshair", "Find your breakpoint",
                                "Tag your mistakes with a reason (why the wrong answer fooled you). "
                                "Then this page shows the trap that catches you most.", "Tag mistakes")
        self.empty.action.clicked.connect(self._tag_untagged)
        self.body.addWidget(self.empty)

        # ---- hero: the breakpoint and what to do
        self.hero = Card(padding=22)
        top = QHBoxLayout()
        top.setSpacing(16)
        self.hero_icon = QLabel()
        self.hero_icon.setFixedSize(56, 56)
        self.hero_icon.setAlignment(Qt.AlignCenter)
        self.hero_icon.setStyleSheet(f"border: 1px solid {T.RED}; border-radius: 28px;")
        top.addWidget(self.hero_icon, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("YOUR BREAKPOINT", "eyebrow"))
        self.hero_name = label("", "display-sm")
        self.hero_name.setWordWrap(True)
        col.addWidget(self.hero_name)
        self.hero_share = label("", "muted")
        col.addWidget(self.hero_share)
        top.addLayout(col, 1)
        self.hero_trend = label("", "eyebrow")
        top.addWidget(self.hero_trend, 0, Qt.AlignTop)
        self.hero.layout().addLayout(top)
        self.hero.layout().addSpacing(4)
        self.hero.layout().addWidget(label("WHAT TO DO", "eyebrow"))
        self.hero_tip = label("")
        self.hero_tip.setWordWrap(True)
        self.hero_tip.setStyleSheet("font-size: 15px;")
        self.hero.layout().addWidget(self.hero_tip)
        acts = QHBoxLayout()
        acts.setSpacing(8)
        self.drill = button("Drill these", "primary", "play")
        self.drill.clicked.connect(lambda: self._drill(self.top_key))
        self.see = button("See them", None, "book-x")
        self.see.clicked.connect(lambda: self._see(self.top_key))
        acts.addWidget(self.drill)
        acts.addWidget(self.see)
        acts.addStretch(1)
        self.untagged = QPushButton()
        self.untagged.setCursor(Qt.PointingHandCursor)
        self.untagged.setProperty("kind", "ghost")
        self.untagged.clicked.connect(self._tag_untagged)
        acts.addWidget(self.untagged)
        self.hero.layout().addLayout(acts)
        self.body.addWidget(self.hero)

        # ---- ranking
        self.rank_card = Card()
        self.rank_card.layout().addWidget(label("Which trap catches you", "h2"))
        self.rank_card.layout().addWidget(label(
            "Every reason, most common first. The right column is your quiz accuracy on it. "
            "Click one to look closer.", "caption"))
        self.bars = ReasonBars()
        self.bars.selected.connect(self._select)
        self.rank_card.layout().addWidget(self.bars)
        self.body.addWidget(self.rank_card)

        # ---- time + where (full width, so every label fits)
        self.time_card = Card()
        self.time_card.layout().addWidget(label("Is it going away?", "h2"))
        self.time_card.layout().addWidget(label("Mistakes per week, last 8 weeks. Hover a dot.", "caption"))
        self.timeline = ReasonTimeline()
        self.time_card.layout().addWidget(self.timeline)
        self.body.addWidget(self.time_card)
        self.where_card = Card()
        self.where_card.layout().addWidget(label("Where it hits", "h2"))
        self.where_card.layout().addWidget(label("Reason × mistake type. Red ring = your worst combo.",
                                                 "caption"))
        self.matrix = ReasonMatrix()
        self.where_card.layout().addWidget(self.matrix)
        self.body.addWidget(self.where_card)

        # ---- examples of the selected reason
        self.ex_card = Card()
        head = QHBoxLayout()
        self.ex_title = label("", "h2")
        head.addWidget(self.ex_title, 1)
        self.ex_drill = button("Drill", None, "play")
        self.ex_drill.clicked.connect(lambda: self._drill(self.sel))
        head.addWidget(self.ex_drill)
        self.ex_card.layout().addLayout(head)
        self.ex_tip = label("", "caption")
        self.ex_tip.setWordWrap(True)
        self.ex_card.layout().addWidget(self.ex_tip)
        self.ex_list = QVBoxLayout()
        self.ex_list.setSpacing(2)
        self.ex_card.layout().addLayout(self.ex_list)
        self.body.addWidget(self.ex_card)
        self.body.addStretch(1)
        self.top_key = None

    # ---- data
    def refresh(self):
        self.stats = db.reason_stats()
        bp = db.breakpoint(self.stats)
        has = bp is not None
        self.empty.setVisible(not has)
        for w in (self.hero, self.rank_card, self.time_card, self.where_card, self.ex_card):
            w.setVisible(has)
        if not has:
            n = self.stats["untagged"]
            self.empty.action.setVisible(n > 0)
            return
        self.top_key = bp["key"]
        if self.sel not in db.REASON:
            self.sel = bp["key"]
        # hero
        self.hero_icon.setPixmap(T.icon_pixmap(bp["icon"], T.RED, 28))
        self.hero_name.setText(bp["name"])
        self.hero_share.setText(f"{bp['share'] * 100:.0f}% of your tagged mistakes · "
                                f"{bp['count']} of {self.stats['tagged']}")
        text, color = _trend(bp)
        self.hero_trend.setText(text)
        self.hero_trend.setStyleSheet(f"color: {color};")
        self.hero_trend.setToolTip(f"Last 14 days: {bp['recent']} · the 14 days before: {bp['prev']}")
        self.hero_tip.setText(bp["tip"])
        n_drill = len(db.quiz_pool(reason=bp["key"]))
        self.drill.setText(f"Drill these ({n_drill})")
        self.drill.setEnabled(n_drill > 0)
        self.drill.setToolTip("" if n_drill else "Add the correct answers to these mistakes to quiz them")
        un = self.stats["untagged"]
        self.untagged.setVisible(un > 0)
        self.untagged.setText(f"{un} mistake{'s' * (un != 1)} have no reason yet · tag them ›")
        # charts
        self.bars.set_data(self.stats["reasons"], bp["key"], self.sel)
        start, weeks = db.reason_by_week()
        self.timeline.set_data(start, weeks, self.sel)
        cells, types = db.reason_by_type()
        self.matrix.set_data(cells, types, self.sel)
        self._fill_examples()

    def _select(self, key):
        self.sel = key
        self.timeline.set_selected(key)
        self.matrix.set_selected(key)
        self._fill_examples()

    def _fill_examples(self):
        r = db.REASON[self.sel]
        self.ex_title.setText(r["name"])
        self.ex_tip.setText(f"{r['desc']}. What to do: {r['tip']}")
        clear_layout(self.ex_list)
        rows = db.all_mistakes(reason=self.sel)[:5]
        self.ex_drill.setEnabled(bool(db.quiz_pool(reason=self.sel)))
        if not rows:
            self.ex_list.addWidget(label("None yet. Nice.", "muted"))
            return
        for m in rows:
            b = QPushButton()
            b.setCursor(Qt.PointingHandCursor)
            b.setAccessibleName(f"Open {m['set_name']} {m['practice_name']}")
            b.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 12px; min-height: 38px; padding: 0 8px; }}"
                f"QPushButton:hover {{ background: {T.RAISED}; }}"
                f"QPushButton:focus {{ border: 1px solid {T.TEXT}; }}")
            hl = QHBoxLayout(b)
            hl.setContentsMargins(10, 0, 10, 0)
            wrong = label(m["wrong"] or "—")
            wrong.setStyleSheet(f"color: {T.RED_TEXT};")
            hl.addWidget(wrong)
            hl.addWidget(label("→", "muted"))
            hl.addWidget(label(m["correct"] or "—"))
            hl.addStretch(1)
            hl.addWidget(label(f"{m['set_name']} · {m['practice_name']}", "caption"))
            for i in range(hl.count()):
                w = hl.itemAt(i).widget()
                if w:
                    w.setAttribute(Qt.WA_TransparentForMouseEvents)
            b.clicked.connect(lambda _=False, pid=m["practice_id"]: self.win.open_practice(pid))
            self.ex_list.addWidget(b)

    # ---- actions
    def _drill(self, key):
        self.win.go_page(self.win.QUIZ)
        self.win.quiz.start_for_reason(key)

    def _see(self, key):
        self.win.go_page(self.win.MISTAKES)
        self.win.mistakes.show_reason(key)

    def _tag_untagged(self):
        self.win.go_page(self.win.MISTAKES)
        self.win.mistakes.show_reason(db.UNTAGGED)
        self.win.toast("Double-click the Reason cell (or right-click) to tag each one", 2600)
