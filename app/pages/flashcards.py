"""Flashcards: word list → review session (flip + Leitner grading) → finish screen."""
from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLineEdit,
                               QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import db
from .. import theme as T
from ..widgets.cards import Card, EmptyState, FlipCard, IconBadge, ProgressBar, button, label
from ..widgets.dialog import ImportDialog, confirm
from ..widgets.toast import AnimatedStack
from .base import Page

EDITABLE = ("word", "meaning", "example", "synonyms")

AI_PROMPT = """Turn the words below into TOEFL flashcards.
Output ONLY lines in this exact format, one per line:
word:meaning
No numbering, bullets, quotes, headings or extra text.
Keep each meaning short and simple (under 12 words).
If I already gave a meaning for a word, keep it.
Example:
car:vehicle you use to transport
lie:you don't say the right thing

Words:
"""


def import_preview(text, update_existing):
    """Summary line for the paste dialog, and whether there's anything to import."""
    pairs, problems = db.parse_card_lines(text)
    if not pairs and not problems:
        return "Paste your list above to see a preview.", False
    have = db.existing_words()
    seen, new, existing = set(), 0, 0
    for w, _ in pairs:
        k = w.lower()
        if k in seen:
            continue
        seen.add(k)
        if k in have:
            existing += 1
        else:
            new += 1
    parts = [f"{new} new card{'s' * (new != 1)}"]
    if existing:
        parts.append(f"{existing} already exist{'s' * (existing == 1)}"
                     + (" (meaning will be updated)" if update_existing else " (skipped)"))
    if problems:
        shown = ", ".join(f"line {n}: {why}" for n, why in problems[:3])
        more = f" +{len(problems) - 3} more" if len(problems) > 3 else ""
        parts.append(f"skipped {shown}{more}")
    return " · ".join(parts), bool(new or (existing and update_existing))


def due_text(due: str) -> str:
    days = (date.fromisoformat(due) - date.today()).days
    if days <= 0:
        return "Today"
    return "Tomorrow" if days == 1 else f"In {days} days"


def box_dots(box: int) -> str:
    return "●" * box + "○" * (len(db.BOX_DAYS) - 1 - box)


# ---------------------------------------------------------------- word list
class WordList(Page):
    def __init__(self, win, owner):
        super().__init__(win, "Flashcards", "", scroll=False)
        self.owner = owner
        paste = self.add_action(button("Paste list", None, "copy"))
        paste.setToolTip("Import many cards at once as word:meaning lines")
        paste.clicked.connect(self._paste)
        self.study_all = self.add_action(button("Study all", None, "shuffle"))
        self.study_all.setToolTip("Review every card now, even ones not due yet")
        self.study_all.clicked.connect(lambda: owner.start(all_cards=True))
        self.review_btn = self.add_action(button("Review", "primary", "play"))
        self.review_btn.clicked.connect(lambda: owner.start())

        entry = QHBoxLayout()
        entry.setSpacing(8)
        self.inputs = {}
        for key, ph, stretch in (("word", "Word", 2), ("meaning", "Meaning", 3),
                                 ("example", "Example sentence (optional)", 3),
                                 ("synonyms", "Synonyms (optional)", 2)):
            e = QLineEdit(placeholderText=ph)
            e.setAccessibleName(ph)
            e.returnPressed.connect(self._add)
            self.inputs[key] = e
            entry.addWidget(e, stretch)
        add = button("Add", "primary", "plus")
        add.clicked.connect(self._add)
        entry.addWidget(add)
        self.body.addLayout(entry)

        self.search = QLineEdit(placeholderText="Search your words…")
        self.search.addAction(T.icon("search", T.MUTED, 16), QLineEdit.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search words")
        self._debounce = QTimer(self, singleShot=True, interval=200, timeout=self._reload)
        self.search.textChanged.connect(lambda: self._debounce.start())
        self.body.addWidget(self.search)

        self.stack = QStackedWidget()
        card = Card(padding=6)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Word", "Meaning", "Example", "Synonyms", "Level",
                                              "Next review", ""])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for i in range(4):
            hh.setSectionResizeMode(i, QHeaderView.Stretch)
        for i, w in ((4, 118), (5, 110), (6, 44)):
            hh.setSectionResizeMode(i, QHeaderView.Fixed)
            hh.resizeSection(i, w)
        self.table.itemChanged.connect(self._cell_changed)
        card.layout().addWidget(self.table)
        self.stack.addWidget(card)
        self.empty = EmptyState("sparkles", "No flashcards yet",
                                "Type a word and its meaning above, paste a whole list with "
                                "“Paste list”, or use “Add to flashcards” on any mistake.")
        self.stack.addWidget(self.empty)
        self.body.addWidget(self.stack, 1)

    def refresh(self):
        self._reload()

    def _reload(self):
        cards = db.list_cards(self.search.text().strip())
        total = len(db.list_cards())
        due = len(db.due_cards())
        self.subtitle.setText(f"{total} word{'s' * (total != 1)} · {due} due today"
                              if total else "Learn the words you keep missing")
        self.review_btn.setText(f"Review {due}" if due else "Nothing due")
        self.review_btn.setEnabled(due > 0)
        self.study_all.setVisible(total > 0)
        self.stack.setCurrentIndex(0 if cards or self.search.text().strip() else 1)
        self.table.blockSignals(True)
        self.table.setRowCount(len(cards))
        for r, c in enumerate(cards):
            for col, key in enumerate(EDITABLE):
                it = QTableWidgetItem(c[key])
                it.setData(Qt.UserRole, c["id"])
                it.setToolTip(c[key])
                if key == "word":
                    it.setForeground(QColor(T.TEXT))
                    f = it.font()
                    f.setWeight(f.Weight.DemiBold)
                    it.setFont(f)
                elif key != "meaning":
                    it.setForeground(QColor(T.MUTED))
                self.table.setItem(r, col, it)
            lvl = QTableWidgetItem(box_dots(c["box"]))
            lvl.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            lvl.setForeground(QColor(T.TEXT))
            lvl.setToolTip(f"Box {c['box']} of {len(db.BOX_DAYS) - 1} · {c['reviews']} reviews")
            self.table.setItem(r, 4, lvl)
            nxt = QTableWidgetItem(due_text(c["due"]))
            nxt.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            nxt.setForeground(QColor(T.RED_TEXT if nxt.text() == "Today" else T.MUTED))
            self.table.setItem(r, 5, nxt)
            b = button("", "icon", "trash-2")
            b.setToolTip("Delete card")
            b.setAccessibleName(f"Delete {c['word']}")
            b.clicked.connect(lambda _=False, cid=c["id"], w=c["word"]: self._delete(cid, w))
            host = QWidget()
            hl = QHBoxLayout(host)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(b, 0, Qt.AlignCenter)
            self.table.setCellWidget(r, 6, host)
        self.table.blockSignals(False)

    def _add(self):
        v = {k: e.text().strip() for k, e in self.inputs.items()}
        if not v["word"]:
            self.inputs["word"].setFocus()
            self.win.toast("Type a word first")
            return
        db.add_card(**v)
        for e in self.inputs.values():
            e.clear()
        self.inputs["word"].setFocus()
        self._reload()
        self.win.toast(f"Added “{v['word']}”")

    def _paste(self):
        d = ImportDialog(self.win, import_preview, AI_PROMPT, self.win.toast)
        if d.exec() != ImportDialog.Accepted:
            return
        text, update = d.values()
        pairs, _ = db.parse_card_lines(text)
        added, updated, skipped = db.import_cards(pairs, update)
        self._reload()
        msg = f"Imported {added} card{'s' * (added != 1)}"
        if updated:
            msg += f", updated {updated}"
        if skipped:
            msg += f", skipped {skipped}"
        self.win.toast(msg)

    def _cell_changed(self, it):
        if it.column() < len(EDITABLE):
            db.update_card(it.data(Qt.UserRole), EDITABLE[it.column()], it.text().strip())
            self.win.toast("Saved", 900)

    def _delete(self, cid, word):
        if confirm(self.win, f"Delete “{word}”?", "This removes the flashcard and its progress."):
            db.delete_card(cid)
            self._reload()
            self.win.toast("Card deleted")


# ---------------------------------------------------------------- review session
GRADES = ((db.AGAIN, "Again", T.RED_TEXT), (db.HARD, "Hard", T.MID),
          (db.GOOD, "Good", T.TEXT), (db.EASY, "Easy", T.TEXT))


class Review(Page):
    def __init__(self, win, owner):
        super().__init__(win, "Review", "", scroll=False)
        self.owner = owner
        back = button("Words", "ghost", "chevron-left")
        back.clicked.connect(owner.show_list)
        self.header.insertWidget(0, back, 0, Qt.AlignTop)
        self.count = self.add_action(label("", "muted"))
        self.progress = ProgressBar()
        self.body.addWidget(self.progress)
        self.body.addSpacing(8)

        self.stack = QStackedWidget()
        self.body.addWidget(self.stack, 1)

        session = QWidget()
        col = QVBoxLayout(session)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(16)
        self.card = FlipCard()
        self.card.flipped.connect(self._on_flip)
        col.addWidget(self.card, 1)
        self.actions = QStackedWidget()
        self.actions.setFixedHeight(56)
        show = QWidget()
        sl = QHBoxLayout(show)
        sl.setContentsMargins(0, 0, 0, 0)
        self.show_btn = button("Show answer   (Space)", "primary")
        self.show_btn.setMinimumWidth(260)
        self.show_btn.clicked.connect(self.card.flip)
        sl.addWidget(self.show_btn, 0, Qt.AlignCenter)
        self.actions.addWidget(show)
        grades = QWidget()
        gl = QHBoxLayout(grades)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(10)
        gl.addStretch(1)
        self.grade_btns = []
        for i, (g, name, color) in enumerate(GRADES):
            b = button(f"{name}   {i + 1}")
            b.setMinimumWidth(120)
            c = QColor(color)
            rgba = lambda a, c=c: f"rgba({c.red()},{c.green()},{c.blue()},{a})"
            b.setStyleSheet(f"QPushButton {{ color: {color}; border-color: {rgba(0.35)}; }}"
                            f"QPushButton:hover {{ background: {rgba(0.12)}; border-color: {color}; }}"
                            f"QPushButton:focus {{ border-color: {color}; }}")
            b.clicked.connect(lambda _=False, g=g: self.grade(g))
            gl.addWidget(b)
            self.grade_btns.append(b)
        gl.addStretch(1)
        self.actions.addWidget(grades)
        col.addWidget(self.actions)
        self.hint = label("Again: see it again now · Hard: tomorrow · Good / Easy: later and later",
                          "caption")
        self.hint.setAlignment(Qt.AlignCenter)
        col.addWidget(self.hint)
        self.stack.addWidget(session)

        # finish screen
        done = QWidget()
        dl = QVBoxLayout(done)
        dl.setAlignment(Qt.AlignCenter)
        dl.setSpacing(8)
        dl.addWidget(IconBadge("circle-check", T.GOOD, 64), 0, Qt.AlignHCenter)
        dl.addSpacing(6)
        t = label("Session complete", "h1")
        t.setAlignment(Qt.AlignCenter)
        dl.addWidget(t)
        self.done_text = label("", "muted")
        self.done_text.setAlignment(Qt.AlignCenter)
        dl.addWidget(self.done_text)
        dl.addSpacing(10)
        back2 = button("Back to words", "primary", "chevron-left", "#FFFFFF")
        back2.clicked.connect(owner.show_list)
        dl.addWidget(back2, 0, Qt.AlignHCenter)
        self.stack.addWidget(done)

        for i, (g, _, _) in enumerate(GRADES):
            sc = QShortcut(QKeySequence(str(i + 1)), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(lambda g=g: self.grade(g) if self.card.is_back() else None)

        self.queue, self.done, self.total, self.good = [], 0, 0, 0

    def start(self, cards):
        self.queue = list(cards)
        self.total = len(cards)
        self.done = self.good = 0
        self.stack.setCurrentIndex(0)
        self._next()

    def _next(self):
        if not self.queue:
            self.progress.set_value(1.0)
            pct = round(100 * self.good / max(1, self.done))
            streak = db.streak()
            self.done_text.setText(f"{self.total} card{'s' * (self.total != 1)} reviewed · {pct}% Good or Easy"
                                   f" · {streak}-day streak")
            self.count.setText("")
            self.stack.setCurrentIndex(1)
            return
        self.card.set_card(self.queue[0])
        self.actions.setCurrentIndex(0)
        self.count.setText(f"{min(self.total - len(self.queue) + 1, self.total)} of {self.total}")
        self.progress.set_value((self.total - len(self.queue)) / max(1, self.total))
        self.card.setFocus()

    def _on_flip(self, back):
        self.actions.setCurrentIndex(1 if back else 0)

    def grade(self, g):
        if not self.queue or not self.card.is_back():
            return
        c = self.queue.pop(0)
        db.review_card(c["id"], g)
        self.done += 1
        if g == db.AGAIN:
            self.queue.append(db.get_card(c["id"]))   # comes back later in this session
        else:
            self.good += g >= db.GOOD
        self._next()

    def refresh(self):
        pass


# ---------------------------------------------------------------- container
class FlashcardsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = AnimatedStack()
        self.list = WordList(win, self)
        self.review = Review(win, self)
        self.stack.addWidget(self.list)
        self.stack.addWidget(self.review)
        lay.addWidget(self.stack)

    def refresh(self):
        self.stack.currentWidget().refresh()

    def show_list(self):
        self.list.refresh()
        self.stack.slide_to(0, -1)

    def start(self, all_cards=False):
        cards = db.list_cards() if all_cards else db.due_cards()
        if not cards:
            self.win.toast("No cards are due. Nice work!")
            return
        self.review.start(cards)
        self.stack.slide_to(1, 1)
