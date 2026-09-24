"""Sets → practices → practice editor, navigated inside one animated stack."""
from PySide6.QtCore import QDate, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDateEdit, QGridLayout, QHBoxLayout,
                               QHeaderView, QLineEdit, QPlainTextEdit, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import db
from .. import theme as T
from ..widgets.cards import Card, EmptyState, IconBadge, ScorePicker, ScorePill, button, label
from ..widgets.dialog import confirm
from ..widgets.reasons import KEY_ROLE, ReasonDelegate, reason_combo, set_reason
from ..widgets.toast import AnimatedStack
from .base import MARGIN, Page, add_card_from_mistake, clear_layout


class Sparkline(QWidget):
    def __init__(self, scores, parent=None):
        super().__init__(parent)
        self._s = scores[-12:]
        self.setFixedHeight(34)

    def paintEvent(self, _):
        if len(self._s) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width() - 8, self.height() - 8
        pts = [QPointF(4 + i * w / (len(self._s) - 1), 4 + h - h * s / 10) for i, s in enumerate(self._s)]
        path = QPainterPath(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.MUTED))
        length = path.length()
        steps = max(2, int(length / 5))
        for k in range(steps + 1):
            p.drawEllipse(path.pointAtPercent(path.percentAtLength(length * k / steps)), 1.1, 1.1)
        p.setBrush(QColor(T.RED if self._s[-1] < 5 else T.TEXT))
        p.drawEllipse(pts[-1], 3.5, 3.5)


def _back(text):
    b = button(text, "ghost", "chevron-left")
    b.setToolTip("Back")
    return b


# ---------------------------------------------------------------- list of sets
class SetsList(Page):
    def __init__(self, win, owner):
        super().__init__(win, "Sets", "Group your practices the way your book or course does")
        self.owner = owner
        add = QHBoxLayout()
        add.setSpacing(8)
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("New set name, e.g. Set 1 or Reading Set A")
        self.new_name.setAccessibleName("New set name")
        self.new_name.returnPressed.connect(self._add)
        add_btn = self.add_btn = button("Add set", "primary", "plus")
        add_btn.clicked.connect(self._add)
        add.addWidget(self.new_name, 1)
        add.addWidget(add_btn)
        self.body.addLayout(add)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 6, 0, 0)
        self.grid.setSpacing(14)
        self.body.addWidget(self.grid_host)
        self.empty = EmptyState("layers", "No sets yet",
                                "Type a name above and press Enter. Sets hold your practices.")
        self.body.addWidget(self.empty)
        self.body.addStretch(1)
        self._cards = []
        self._cols = 0

    def _add(self):
        name = self.new_name.text().strip() or f"Set {len(db.list_sets()) + 1}"
        sid = db.add_set(name)
        self.new_name.clear()
        self.win.toast(f"Created “{name}”")
        self.owner.open_set(sid)

    def refresh(self):
        clear_layout(self.grid)
        self._cards = []
        sets = db.list_sets()
        self.empty.setVisible(not sets)
        self.grid_host.setVisible(bool(sets))
        for s in sets:
            self._cards.append(self._card(s))
        self._cols = 0
        self._layout_cards()

    def _card(self, s):
        c = Card(clickable=True, padding=16)
        c.setAccessibleName(f"Open set {s['name']}")
        c.setMinimumHeight(150)
        top = QHBoxLayout()
        top.addWidget(IconBadge("layers", T.TEXT))
        top.addStretch(1)
        avg = s["avg"]
        pill = ScorePill(None if avg is None else round(avg))
        pill.setToolTip("Average score")
        top.addWidget(pill)
        c.layout().addLayout(top)
        name = label(s["name"], "h2")
        name.setWordWrap(True)
        c.layout().addWidget(name)
        n, m = s["practices"], s["mistakes"]
        avg_txt = f" · avg {avg:.1f}" if avg is not None else ""
        c.layout().addWidget(label(f"{n} practice{'s' * (n != 1)} · {m} mistake{'s' * (m != 1)}{avg_txt}",
                                   "caption"))
        c.layout().addStretch(1)
        c.layout().addWidget(Sparkline(db.set_scores(s["id"])))
        c.clicked.connect(lambda sid=s["id"]: self.owner.open_set(sid))
        return c

    def _layout_cards(self):
        cols = max(1, (self.width() - 2 * MARGIN) // 250)
        if cols == self._cols:
            return
        self._cols = cols
        for c in self._cards:
            self.grid.removeWidget(c)
        for i, c in enumerate(self._cards):
            self.grid.addWidget(c, i // cols, i % cols)
        for i in range(8):
            self.grid.setColumnStretch(i, 1 if i < cols else 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout_cards()


# ---------------------------------------------------------------- one set
class SetDetail(Page):
    def __init__(self, win, owner):
        super().__init__(win)
        self.owner = owner
        self.set_id = None
        self.title.hide()
        back = _back("All sets")
        back.clicked.connect(owner.show_list)
        self.header.insertWidget(0, back, 0, Qt.AlignTop)
        self.name_edit = QLineEdit()
        self.name_edit.setProperty("role", "title")
        self.name_edit.setToolTip("Click to rename")
        self.name_edit.setAccessibleName("Set name")
        self.name_edit.editingFinished.connect(self._rename)
        self.header.itemAt(1).layout().insertWidget(0, self.name_edit)
        del_btn = self.add_action(button("Delete set", "danger", "trash-2", T.DANGER))
        del_btn.clicked.connect(self._delete)
        new_btn = self.add_action(button("New practice", "primary", "plus"))
        new_btn.clicked.connect(self._new_practice)

        self.rows = QVBoxLayout()
        self.rows.setSpacing(8)
        self.body.addLayout(self.rows)
        self.empty = EmptyState("file-text", "No practices in this set yet",
                                "Add a practice, then log your score and the answers you missed.",
                                "New practice")
        self.empty.action.clicked.connect(self._new_practice)
        self.body.addWidget(self.empty)
        self.body.addStretch(1)

    def load(self, set_id):
        self.set_id = set_id
        self.refresh()

    def refresh(self):
        s = db.get_set(self.set_id)
        if not s:
            return
        self.name_edit.setText(s["name"])
        practices = db.list_practices(self.set_id)
        scored = [p["score"] for p in practices if p["score"] is not None]
        mistakes = sum(p["mistakes"] for p in practices)
        avg = f" · average {sum(scored) / len(scored):.1f}/10" if scored else ""
        self.subtitle.setText(f"{len(practices)} practices · {mistakes} mistakes{avg}")
        clear_layout(self.rows)
        self.empty.setVisible(not practices)
        for i, p in enumerate(practices, 1):
            self.rows.addWidget(self._row(i, p))

    def _row(self, i, p):
        c = Card(clickable=True, radius=12, padding=12)
        c.setAccessibleName(f"Open {p['name']}")
        lay = QHBoxLayout()
        lay.setSpacing(12)
        num = label(str(i), "h2")
        num.setFixedWidth(30)
        num.setAlignment(Qt.AlignCenter)
        num.setStyleSheet(f"background: {T.RAISED}; border-radius: 8px; color: {T.MUTED}; padding: 4px 0;")
        lay.addWidget(num)
        txt = QVBoxLayout()
        txt.setSpacing(1)
        txt.addWidget(label(p["name"]))
        m = p["mistakes"]
        txt.addWidget(label(f"{p['date']} · {m} mistake{'s' * (m != 1)}", "caption"))
        lay.addLayout(txt, 1)
        lay.addWidget(ScorePill(p["score"]))
        c.layout().addLayout(lay)
        c.clicked.connect(lambda pid=p["id"]: self.owner.open_practice(pid))
        return c

    def _rename(self):
        name = self.name_edit.text().strip()
        s = db.get_set(self.set_id)
        if s and name and name != s["name"]:
            db.rename_set(self.set_id, name)
            self.win.toast("Set renamed")
        elif s and not name:
            self.name_edit.setText(s["name"])

    def _new_practice(self):
        pid = db.add_practice(self.set_id)
        self.owner.open_practice(pid)

    def _delete(self):
        s = db.get_set(self.set_id)
        if confirm(self.win, f"Delete “{s['name']}”?",
                   "This removes the set with all of its practices and mistakes. This can't be undone."):
            db.delete_set(self.set_id)
            self.win.toast("Set deleted")
            self.owner.show_list()


# ---------------------------------------------------------------- practice editor
COLS = ("wrong", "correct", "category", "reason", "topic")
ACT = len(COLS)   # the buttons column


class PracticeEditor(Page):
    ROW_H = 38

    def __init__(self, win, owner):
        super().__init__(win)
        self.owner = owner
        self.pid = None
        self._loading = False
        self.title.hide()
        self.back = _back("Set")
        self.back.clicked.connect(lambda: owner.open_set(self._set_id, direction=-1))
        self.header.insertWidget(0, self.back, 0, Qt.AlignTop)
        self.name_edit = QLineEdit()
        self.name_edit.setProperty("role", "title")
        self.name_edit.setToolTip("Click to rename")
        self.name_edit.setAccessibleName("Practice name")
        self.name_edit.editingFinished.connect(self._save_name)
        self.header.itemAt(1).layout().insertWidget(0, self.name_edit)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("d MMM yyyy")
        self.date_edit.setAccessibleName("Practice date")
        self.date_edit.dateChanged.connect(self._save_date)
        self.add_action(self.date_edit)
        del_btn = self.add_action(button("Delete", "danger", "trash-2", T.DANGER))
        del_btn.clicked.connect(self._delete)

        # score
        score = Card()
        head = QHBoxLayout()
        head.addWidget(label("Score", "h2"))
        head.addStretch(1)
        self.score_text = label("", "muted")
        head.addWidget(self.score_text)
        score.layout().addLayout(head)
        score.layout().addWidget(label("How many out of 10 did you get right? Click or type a number.",
                                       "caption"))
        self.picker = ScorePicker()
        self.picker.setAccessibleName("Score out of 10")
        self.picker.valueChanged.connect(self._save_score)
        score.layout().addWidget(self.picker)
        self.body.addWidget(score)

        # mistakes
        mc = Card()
        head = QHBoxLayout()
        head.addWidget(label("Mistakes", "h2"))
        head.addStretch(1)
        self.count = label("", "muted")
        head.addWidget(self.count)
        mc.layout().addLayout(head)
        mc.layout().addWidget(label("Log each wrong answer. Press Enter to add it, and double-click "
                                    "a cell to edit it.", "caption"))
        entry = QHBoxLayout()
        entry.setSpacing(8)
        self.in_wrong = QLineEdit(placeholderText="Your answer / wrong word")
        self.in_correct = QLineEdit(placeholderText="Correct answer")
        self.in_cat = QComboBox()
        self.in_cat.setEditable(True)
        self.in_cat.lineEdit().setPlaceholderText("Mistake type")
        self.in_reason = reason_combo()
        self.in_topic = QLineEdit(placeholderText="Topic (optional)")
        for w, name in ((self.in_wrong, "Wrong answer"), (self.in_correct, "Correct answer"),
                        (self.in_cat, "Mistake type"), (self.in_topic, "Topic")):
            w.setAccessibleName(name)
        add_btn = button("Add", "primary", "plus")
        add_btn.clicked.connect(self._add_mistake)
        for w in (self.in_wrong, self.in_correct, self.in_topic, self.in_cat.lineEdit()):
            w.returnPressed.connect(self._add_mistake)
        entry.addWidget(self.in_wrong, 1)
        entry.addWidget(self.in_correct, 1)
        mc.layout().addLayout(entry)
        entry2 = QHBoxLayout()   # second row: why it went wrong
        entry2.setSpacing(8)
        entry2.addWidget(self.in_cat, 2)
        entry2.addWidget(self.in_reason, 3)
        entry2.addWidget(self.in_topic, 2)
        entry2.addWidget(add_btn)
        mc.layout().addLayout(entry2)

        self.table = QTableWidget(0, ACT + 1)
        self.table.setHorizontalHeaderLabels(["Wrong", "Correct", "Type", "Reason", "Topic", ""])
        self.table.setItemDelegateForColumn(COLS.index("reason"), ReasonDelegate(self.table))
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setFocusPolicy(Qt.StrongFocus)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.verticalHeader().setDefaultSectionSize(self.ROW_H)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for i in range(ACT):
            hh.setSectionResizeMode(i, QHeaderView.Stretch)
        hh.setSectionResizeMode(ACT, QHeaderView.Fixed)
        hh.resizeSection(ACT, 80)
        self.table.itemChanged.connect(self._cell_changed)
        mc.layout().addWidget(self.table)
        self.no_mistakes = label("No mistakes logged yet. A perfect score, or just getting started?",
                                 "muted")
        mc.layout().addWidget(self.no_mistakes)
        self.body.addWidget(mc)

        # notes
        nc = Card()
        nc.layout().addWidget(label("Notes", "h2"))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Anything to remember about this practice…")
        self.notes.setAccessibleName("Notes")
        self.notes.setFixedHeight(80)
        self._notes_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save_notes)
        self.notes.textChanged.connect(lambda: None if self._loading else self._notes_timer.start())
        nc.layout().addWidget(self.notes)
        self.body.addWidget(nc)
        self.body.addStretch(1)

    # ---- loading
    def load(self, pid):
        self.pid = pid
        p = db.get_practice(pid)
        if not p:
            return
        self._loading = True
        self._set_id = p["set_id"]
        self.back.setText(p["set_name"])
        self.name_edit.setText(p["name"])
        self.date_edit.setDate(QDate.fromString(p["date"], "yyyy-MM-dd"))
        self.picker.setValue(p["score"], animate=False)
        self._update_score_text(p["score"])
        self.notes.setPlainText(p["notes"])
        self.subtitle.setText(f"In {p['set_name']} · changes save automatically")
        self._reload_categories()
        self._load_table()
        self._loading = False
        self.in_wrong.clear()
        self.in_correct.clear()
        self.in_topic.clear()
        self.in_cat.setEditText("")

    def refresh(self):
        pass  # editor keeps its state; load() is called explicitly

    def _reload_categories(self):
        self.in_cat.clear()
        self.in_cat.addItems(db.categories())
        self.in_cat.setEditText("")

    def _load_table(self):
        rows = db.list_mistakes(self.pid)
        carded = db.card_mistake_ids()
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for m in rows:
            self._append_row(m, m["id"] in carded)
        self.table.blockSignals(False)
        self._fit_table()

    def _append_row(self, m, carded=False):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, key in enumerate(COLS):
            it = QTableWidgetItem(db.reason_name(m[key]) if key == "reason" else m[key])
            it.setData(Qt.UserRole, m["id"])
            if key == "reason":
                it.setData(KEY_ROLE, m[key])
                it.setForeground(QColor(T.MUTED))
                it.setToolTip(db.REASON[m[key]]["desc"] if m[key] in db.REASON else "Double-click to pick a reason")
                if m[key] in db.REASON:
                    it.setIcon(T.icon(db.REASON[m[key]]["icon"], T.MUTED, 16))
            if key == "wrong":
                it.setForeground(QColor(T.DANGER))
            elif key == "correct":
                it.setForeground(QColor(T.GOOD))
            elif key == "category":
                it.setForeground(QColor(T.MUTED))
            self.table.setItem(r, c, it)
        fc = button("", "icon", "check" if carded else "sparkles", T.TEXT if carded else T.RED)
        fc.setToolTip("Already in flashcards" if carded else "Add to flashcards")
        fc.setAccessibleName(fc.toolTip())
        fc.setEnabled(not carded)
        fc.clicked.connect(lambda _=False, mid=m["id"]: self._to_card(mid))
        b = button("", "icon", "trash-2")
        b.setToolTip("Delete mistake")
        b.setAccessibleName("Delete mistake")
        b.clicked.connect(lambda _=False, mid=m["id"]: self._delete_mistake(mid))
        host = QWidget()
        hl = QHBoxLayout(host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(2)
        hl.addWidget(fc, 0, Qt.AlignCenter)
        hl.addWidget(b, 0, Qt.AlignCenter)
        self.table.setCellWidget(r, ACT, host)

    def _fit_table(self):
        n = self.table.rowCount()
        self.table.setVisible(n > 0)
        self.no_mistakes.setVisible(n == 0)
        self.table.setFixedHeight(self.table.horizontalHeader().height() + n * self.ROW_H + 4)
        self.count.setText(f"{n} logged")

    # ---- saving
    def _update_score_text(self, s):
        if s is None:
            self.score_text.setText("Not scored yet")
            self.score_text.setStyleSheet(f"color: {T.MUTED};")
        else:
            self.score_text.setText(f"{s}/10 · {T.score_label(s)}")
            self.score_text.setStyleSheet(f"color: {T.score_color(s)}; font-weight: 600;")

    def _save_score(self, v):
        db.update_practice(self.pid, score=v)
        self._update_score_text(v)
        self.win.toast(f"Score saved: {v}/10")

    def _save_name(self):
        name = self.name_edit.text().strip()
        p = db.get_practice(self.pid)
        if p and name and name != p["name"]:
            db.update_practice(self.pid, name=name)
            self.win.toast("Renamed")
        elif p and not name:
            self.name_edit.setText(p["name"])

    def _save_date(self, d):
        if not self._loading and self.pid:
            db.update_practice(self.pid, date=d.toString("yyyy-MM-dd"))
            self.win.toast("Date saved")

    def _save_notes(self):
        if self.pid:
            db.update_practice(self.pid, notes=self.notes.toPlainText())
            self.win.toast("Notes saved", 1000)

    def _add_mistake(self):
        wrong, correct = self.in_wrong.text().strip(), self.in_correct.text().strip()
        cat, topic = self.in_cat.currentText().strip(), self.in_topic.text().strip()
        if not (wrong or correct):
            self.in_wrong.setFocus()
            self.win.toast("Type the wrong answer or the correct one first")
            return
        reason = self.in_reason.currentData() or ""
        mid = db.add_mistake(self.pid, wrong, correct, cat, topic, reason)
        self.table.blockSignals(True)  # new mistake: never has a card yet
        self._append_row({"id": mid, "wrong": wrong, "correct": correct, "category": cat, "topic": topic,
                          "reason": reason})
        self.table.blockSignals(False)
        self._fit_table()
        self.in_wrong.clear()
        self.in_correct.clear()
        self.in_topic.clear()
        set_reason(self.in_reason, "")   # reasons differ word to word; the type usually doesn't
        if cat and self.in_cat.findText(cat) < 0:
            self.in_cat.addItem(cat)
        self.in_cat.setEditText(cat)   # keep type: mistakes often come in runs of the same type
        self.in_wrong.setFocus()
        self.win.toast("Mistake added")

    def _cell_changed(self, it):
        if it.column() < len(COLS):
            key = COLS[it.column()]
            value = (it.data(KEY_ROLE) or "") if key == "reason" else it.text().strip()
            db.update_mistake(it.data(Qt.UserRole), key, value)
            self.win.toast("Saved", 900)

    def _to_card(self, mid):
        m = next((x for x in db.list_mistakes(self.pid) if x["id"] == mid), None)
        if m and add_card_from_mistake(self.win, m):
            self._load_table()

    def _delete_mistake(self, mid):
        db.delete_mistake(mid)
        self._load_table()
        self.win.toast("Mistake deleted")

    def flush(self):
        """Persist pending edits before leaving the editor."""
        if self._notes_timer.isActive():
            self._notes_timer.stop()
            self._save_notes()

    def _delete(self):
        p = db.get_practice(self.pid)
        if confirm(self.win, f"Delete “{p['name']}”?",
                   "This removes the practice and every mistake logged in it. This can't be undone."):
            self._notes_timer.stop()
            db.delete_practice(self.pid)
            self.win.toast("Practice deleted")
            self.owner.open_set(p["set_id"], direction=-1)


# ---------------------------------------------------------------- container
class SetsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = AnimatedStack()
        self.list = SetsList(win, self)
        self.detail = SetDetail(win, self)
        self.editor = PracticeEditor(win, self)
        for w in (self.list, self.detail, self.editor):
            self.stack.addWidget(w)
        lay.addWidget(self.stack)

    def refresh(self):
        self.stack.currentWidget().refresh()

    def _leave_editor(self):
        if self.stack.currentWidget() is self.editor:
            self.editor.flush()

    def show_list(self):
        self._leave_editor()
        self.list.refresh()
        self.stack.slide_to(0, -1)

    def open_set(self, set_id, direction=1):
        self._leave_editor()
        self.detail.load(set_id)
        self.stack.slide_to(1, direction)

    def open_practice(self, pid):
        self._leave_editor()
        self.editor.load(pid)
        self.stack.slide_to(2, 1)
        self.editor.picker.setFocus() if self.editor.picker.value() is None else self.editor.in_wrong.setFocus()

    def focus_new(self):
        self.show_list()
        self.list.new_name.setFocus()
