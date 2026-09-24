"""Quiz from your own mistakes: setup → questions → summary."""
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from .. import db
from .. import theme as T
from ..widgets.cards import Card, EmptyState, IconBadge, ProgressBar, button, label, shake
from ..widgets.toast import AnimatedStack
from .base import Page, add_card_from_mistake, clear_layout

COUNTS = (("10 questions", 10), ("20 questions", 20), ("All", None))


class QuizSetup(Page):
    def __init__(self, win, owner):
        super().__init__(win, "Quiz", "Test yourself on the answers you got wrong")
        self.owner = owner
        self.card = Card(padding=22)
        self.card.setFixedWidth(640)
        self.card.layout().addWidget(label("New quiz", "h2"))
        self.card.layout().addWidget(label(
            "You'll see your wrong answer and type the correct one. Mistakes you've never been quizzed "
            "on come first, then the ones you missed most recently.", "caption"))
        self.card.layout().itemAt(1).widget().setWordWrap(True)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.set_filter = QComboBox()
        self.set_filter.setAccessibleName("Set")
        self.cat = QComboBox()
        self.cat.setAccessibleName("Mistake type")
        self.count = QComboBox()
        self.count.setAccessibleName("Number of questions")
        for text, n in COUNTS:
            self.count.addItem(text, n)
        for w in (self.set_filter, self.cat, self.count):
            w.currentIndexChanged.connect(self._update_pool)
            row.addWidget(w, 1)
        self.card.layout().addLayout(row)
        foot = QHBoxLayout()
        self.pool = label("", "muted")
        foot.addWidget(self.pool, 1)
        self.start_btn = button("Start quiz", "primary", "play")
        self.start_btn.clicked.connect(self._start)
        foot.addWidget(self.start_btn)
        self.card.layout().addLayout(foot)
        self.body.addWidget(self.card, 0, Qt.AlignHCenter)
        self.empty = EmptyState("brain", "Nothing to quiz yet",
                                "Log some mistakes with their correct answers in a practice, "
                                "then come back here to test yourself.")
        self.body.addWidget(self.empty)
        self.body.addStretch(1)
        self._filling = False

    def refresh(self):
        self._filling = True
        cur_set, cur_cat = self.set_filter.currentData(), self.cat.currentData()
        self.set_filter.clear()
        self.set_filter.addItem("All sets", None)
        for s in db.list_sets():
            self.set_filter.addItem(s["name"], s["id"])
        self.cat.clear()
        self.cat.addItem("All types", "")
        for c in db.used_categories():
            self.cat.addItem(c, c)
        self.set_filter.setCurrentIndex(max(0, self.set_filter.findData(cur_set)))
        self.cat.setCurrentIndex(max(0, self.cat.findData(cur_cat)))
        self._filling = False
        has_any = bool(db.quiz_pool())
        self.card.setVisible(has_any)
        self.empty.setVisible(not has_any)
        self._update_pool()

    def _pool(self):
        return db.quiz_pool(self.set_filter.currentData(), self.cat.currentData() or "",
                            self.count.currentData())

    def _update_pool(self):
        if self._filling:
            return
        total = len(db.quiz_pool(self.set_filter.currentData(), self.cat.currentData() or ""))
        n = len(self._pool())
        self.pool.setText(f"{n} of {total} mistake{'s' * (total != 1)} in this quiz")
        self.start_btn.setEnabled(n > 0)

    def _start(self):
        self.owner.start(self._pool())


class QuizRun(Page):
    def __init__(self, win, owner):
        super().__init__(win, "Quiz", "", scroll=False)
        self.owner = owner
        back = button("End quiz", "ghost", "chevron-left")
        back.clicked.connect(owner.show_setup)
        self.header.insertWidget(0, back, 0, Qt.AlignTop)
        self.counter = self.add_action(label("", "muted"))
        self.progress = ProgressBar()
        self.body.addWidget(self.progress)
        self.body.addSpacing(16)

        self.q = Card(padding=26)
        self.q.setMaximumWidth(640)
        ql = self.q.layout()
        ql.setSpacing(10)
        self.meta = label("", "eyebrow")
        ql.addWidget(self.meta)
        ql.addWidget(label("What's the correct answer?", "h2"))
        self.you = label("", "muted")
        self.you.setWordWrap(True)
        ql.addWidget(self.you)
        self.answer = QLineEdit(placeholderText="Type the correct answer and press Enter")
        self.answer.setAccessibleName("Your answer")
        self.answer.setStyleSheet("font-size: 17px; padding: 10px 12px;")
        self.answer.returnPressed.connect(self._enter)
        ql.addWidget(self.answer)
        self.result = label("")
        self.result.setWordWrap(True)
        self.result.setMinimumHeight(24)
        ql.addWidget(self.result)
        btns = QHBoxLayout()
        self.source = label("", "caption")
        btns.addWidget(self.source, 1)
        self.override = button("I was right", "ghost", "check")
        self.override.setToolTip("Count it as correct (e.g. a synonym or a different spelling)")
        self.override.clicked.connect(self._override)
        self.card_btn = button("Add to flashcards", "ghost", "sparkles")
        self.card_btn.clicked.connect(self._add_card)
        self.main = button("Check", "primary")
        self.main.clicked.connect(self._enter)
        for b in (self.card_btn, self.override, self.main):
            btns.addWidget(b)
        ql.addLayout(btns)
        wrap = QHBoxLayout()
        wrap.addWidget(self.q)
        self.body.addLayout(wrap)
        self.body.addStretch(1)
        self.items, self.i, self.checked, self.results = [], 0, False, []

    def start(self, items):
        self.items, self.i, self.results = list(items), 0, []
        self._show()

    def _show(self):
        m = self.items[self.i]
        self.checked = False
        meta = " · ".join(x for x in (m["category"], m["topic"]) if x) or "Mistake"
        self.meta.setText(meta.upper())
        self.you.setText(f"You answered: <span style='color:{T.DANGER}'>{escape(m['wrong']) or '(blank)'}</span>")
        self.source.setText(f"From {m['set_name']} · {m['practice_name']}")
        self.answer.clear()
        self.answer.setReadOnly(False)
        self.answer.setStyleSheet("font-size: 17px; padding: 10px 12px;")
        self.result.setText("")
        self.override.hide()
        self.card_btn.hide()
        self.main.setText("Check")
        self.counter.setText(f"{self.i + 1} of {len(self.items)}")
        self.progress.set_value(self.i / len(self.items))
        self.answer.setFocus()

    def _enter(self):
        if not self.checked:
            self._check()
        else:
            self._next()

    def _check(self):
        m = self.items[self.i]
        ok = db.is_correct(self.answer.text(), m["correct"])
        db.log_quiz(m["id"], ok)
        self.results.append(ok)
        self.checked = True
        self.answer.setReadOnly(True)
        color = T.GOOD if ok else T.DANGER
        self.answer.setStyleSheet(f"font-size: 17px; padding: 10px 12px; border-color: {color};")
        if ok:
            self.result.setText(f"<span style='color:{T.GOOD}; font-weight:600'>✓ Correct</span>")
        else:
            self.result.setText(f"<span style='color:{T.DANGER}; font-weight:600'>✗ Not quite.</span>"
                                f" &nbsp;Correct answer: <b style='color:{T.GOOD}'>{escape(m['correct'])}</b>")
            self.override.setVisible(bool(self.answer.text().strip()))
            shake(self.q)
        self.card_btn.setVisible(m["id"] not in db.card_mistake_ids())
        self.main.setText("Finish" if self.i == len(self.items) - 1 else "Next")

    def _override(self):
        m = self.items[self.i]
        db.log_quiz(m["id"], True)   # newest log entry wins for ordering
        self.results[-1] = True
        self.override.hide()
        self.answer.setStyleSheet(f"font-size: 17px; padding: 10px 12px; border-color: {T.GOOD};")
        self.result.setText(f"<span style='color:{T.GOOD}; font-weight:600'>✓ Counted as correct</span>")

    def _add_card(self):
        if add_card_from_mistake(self.win, self.items[self.i]):
            self.card_btn.hide()

    def _next(self):
        self.i += 1
        if self.i >= len(self.items):
            self.owner.finish(self.items, self.results)
        else:
            self._show()

    def refresh(self):
        pass


class QuizSummary(Page):
    def __init__(self, win, owner):
        super().__init__(win, "Quiz results", "")
        self.owner = owner
        top = QHBoxLayout()
        top.setSpacing(16)
        self.badge_host = QHBoxLayout()
        top.addLayout(self.badge_host)
        txt = QVBoxLayout()
        self.score = label("", "h1")
        self.note = label("", "muted")
        txt.addWidget(self.score)
        txt.addWidget(self.note)
        top.addLayout(txt, 1)
        self.retry = button("Retry missed", "primary", "rotate-ccw")
        self.retry.clicked.connect(lambda: owner.start(self._missed))
        new = button("New quiz")
        new.clicked.connect(owner.show_setup)
        top.addWidget(new)
        top.addWidget(self.retry)
        self.body.addLayout(top)
        self.missed_card = Card()
        self.missed_card.layout().addWidget(label("Review these", "h2"))
        self.rows = QVBoxLayout()
        self.rows.setSpacing(6)
        self.missed_card.layout().addLayout(self.rows)
        self.body.addWidget(self.missed_card)
        self.body.addStretch(1)
        self._missed = []

    def show_results(self, items, results):
        n, ok = len(items), sum(results)
        self._missed = [m for m, r in zip(items, results) if not r]
        clear_layout(self.badge_host)
        good = ok / n >= 0.8
        self.badge_host.addWidget(IconBadge("circle-check" if good else "target",
                                            T.TEXT if good else T.RED, 56))
        self.score.setText(f"{ok} / {n} correct")
        self.note.setText("Excellent. These are sticking." if good else
                          "Good practice. Retry the missed ones while they're fresh.")
        self.retry.setVisible(bool(self._missed))
        clear_layout(self.rows)
        self.missed_card.setVisible(bool(self._missed))
        for m in self._missed:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 4, 0, 4)
            w = label(m["wrong"] or "(blank)")
            w.setStyleSheet(f"color: {T.DANGER};")
            arrow = label("→", "muted")
            c = label(m["correct"])
            c.setStyleSheet(f"color: {T.GOOD}; font-weight: 600;")
            rl.addWidget(w)
            rl.addWidget(arrow)
            rl.addWidget(c)
            rl.addStretch(1)
            rl.addWidget(label(" · ".join(x for x in (m["category"], m["topic"]) if x), "caption"))
            self.rows.addWidget(row)


class QuizPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = AnimatedStack()
        self.setup = QuizSetup(win, self)
        self.run = QuizRun(win, self)
        self.summary = QuizSummary(win, self)
        for w in (self.setup, self.run, self.summary):
            self.stack.addWidget(w)
        lay.addWidget(self.stack)

    def refresh(self):
        if self.stack.currentWidget() is self.setup:
            self.setup.refresh()

    def show_setup(self):
        self.setup.refresh()
        self.stack.slide_to(0, -1)

    def start(self, items):
        if not items:
            return
        self.run.start(items)
        self.stack.slide_to(1, 1)

    def finish(self, items, results):
        self.summary.show_results(items, results)
        self.stack.slide_to(2, 1)
