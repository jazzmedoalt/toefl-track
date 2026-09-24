from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLineEdit,
                               QMenu, QStackedWidget, QTableWidget, QTableWidgetItem)

from .. import db
from .. import theme as T
from ..widgets.cards import Card, EmptyState, button, label
from ..widgets.reasons import KEY_ROLE, ReasonDelegate, reason_combo, set_reason
from .base import Page, add_card_from_mistake


REASON_COL = 3
MID_ROLE = Qt.UserRole + 2


class MistakesPage(Page):
    def __init__(self, win):
        super().__init__(win, "Mistakes", "Every wrong answer in one place. Review these before the test.",
                         scroll=False)
        self.count = self.add_action(label("", "muted"))
        self.card_btn = self.add_action(button("Add to flashcards", None, "sparkles", T.RED))
        self.card_btn.setToolTip("Turn the selected mistake into a flashcard")
        self.card_btn.clicked.connect(self._card_selected)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.search = QLineEdit(placeholderText="Search words, answers, topics…")
        self.search.addAction(T.icon("search", T.MUTED, 16), QLineEdit.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search mistakes")
        self._debounce = QTimer(self, singleShot=True, interval=200, timeout=self.refresh)
        self.search.textChanged.connect(lambda: self._debounce.start())
        self.cat = QComboBox()
        self.cat.setAccessibleName("Filter by type")
        self.cat.setMinimumWidth(160)
        self.set_filter = QComboBox()
        self.set_filter.setAccessibleName("Filter by set")
        self.set_filter.setMinimumWidth(160)
        self.reason = reason_combo("All reasons")
        self.reason.addItem(T.icon("circle-help", T.MUTED, 16), "No reason yet", db.UNTAGGED)
        self.reason.setAccessibleName("Filter by reason")
        self.reason.setMinimumWidth(190)
        self.reason.currentIndexChanged.connect(lambda: self._reload())
        self.cat.currentIndexChanged.connect(lambda: self._reload())
        self.set_filter.currentIndexChanged.connect(lambda: self._reload())
        bar.addWidget(self.search, 1)
        bar.addWidget(self.cat)
        bar.addWidget(self.reason)
        bar.addWidget(self.set_filter)
        self.body.addLayout(bar)

        self.stack = QStackedWidget()
        card = Card(padding=6)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Wrong", "Correct", "Type", "Reason", "Topic", "From"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.ElideRight)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setToolTip("Double-click a row to open its practice. Right-click for more.")
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemSelectionChanged.connect(self._update_card_btn)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setSectionResizeMode(QHeaderView.Stretch)
        self.table.setItemDelegateForColumn(REASON_COL, ReasonDelegate(self.table))
        self.table.itemChanged.connect(self._reason_changed)
        self.table.cellDoubleClicked.connect(self._double)
        self.table.cellActivated.connect(self._open)
        card.layout().addWidget(self.table)
        self.stack.addWidget(card)
        self.empty = EmptyState("book-x", "Nothing here yet",
                                "Mistakes you log in a practice show up here, so you can review "
                                "them all together.")
        self.stack.addWidget(self.empty)
        self.body.addWidget(self.stack, 1)
        self._filling = False
        self._rows, self._carded = [], set()

    def _fill_filters(self):
        self._filling = True
        cur_cat, cur_set = self.cat.currentData(), self.set_filter.currentData()
        self.cat.clear()
        self.cat.addItem("All types", "")
        for c in db.used_categories():
            self.cat.addItem(c, c)
        self.set_filter.clear()
        self.set_filter.addItem("All sets", None)
        for s in db.list_sets():
            self.set_filter.addItem(s["name"], s["id"])
        self.cat.setCurrentIndex(max(0, self.cat.findData(cur_cat)))
        self.set_filter.setCurrentIndex(max(0, self.set_filter.findData(cur_set)))
        self._filling = False

    def refresh(self):
        self._fill_filters()
        self._reload()

    def show_reason(self, key):
        """Open filtered to one reason (or to untagged mistakes when key is '')."""
        self.search.clear()
        self._filling = True
        self.cat.setCurrentIndex(0)
        self.set_filter.setCurrentIndex(0)
        self._filling = False
        set_reason(self.reason, key)
        self._reload()

    def _reload(self):
        if self._filling:
            return
        rows = db.all_mistakes(self.search.text().strip(), self.cat.currentData() or "",
                               self.set_filter.currentData(), self.reason.currentData() or "")
        filtered = bool(self.search.text().strip() or self.cat.currentData() or self.set_filter.currentData()
                        or self.reason.currentData())
        self.count.setText(f"{len(rows)} mistake{'s' * (len(rows) != 1)}")
        self.stack.setCurrentIndex(0 if rows or filtered else 1)
        self._rows = rows
        self._carded = db.card_mistake_ids()
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        colors = {0: T.DANGER, 1: T.GOOD, 2: T.MUTED, 3: T.MUTED, 5: T.MUTED}
        for r, m in enumerate(rows):
            vals = (m["wrong"], m["correct"], m["category"], db.reason_name(m["reason"]), m["topic"],
                    f"{m['set_name']} · {m['practice_name']}")
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setData(Qt.UserRole, m["practice_id"])
                it.setToolTip(v)
                if c == REASON_COL:
                    it.setData(KEY_ROLE, m["reason"])
                    it.setData(MID_ROLE, m["id"])
                    it.setToolTip(db.REASON[m["reason"]]["desc"] if m["reason"] in db.REASON
                                  else "Double-click to pick a reason")
                it.setForeground(QColor(colors.get(c, T.TEXT)))
                self.table.setItem(r, c, it)
            if m["reason"] in db.REASON:
                self.table.item(r, 3).setIcon(T.icon(db.REASON[m["reason"]]["icon"], T.MUTED, 16))
            if m["id"] in self._carded:
                self.table.item(r, 0).setIcon(T.icon("sparkles", T.RED, 14))
                self.table.item(r, 0).setToolTip("In flashcards")
        self.table.blockSignals(False)
        self._update_card_btn()

    def _double(self, row, col):
        if col == REASON_COL:
            self.table.editItem(self.table.item(row, col))
        else:
            self._open(row, col)

    def _reason_changed(self, it):
        if it.column() == REASON_COL and it.data(MID_ROLE):
            db.update_mistake(it.data(MID_ROLE), "reason", it.data(KEY_ROLE) or "")
            self.win.toast("Reason saved", 1000)

    def _open(self, row, _col):
        it = self.table.item(row, 0)
        if it:
            self.win.open_practice(it.data(Qt.UserRole))

    def _selected(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return self._rows[rows[0].row()] if rows else None

    def _update_card_btn(self):
        m = self._selected()
        self.card_btn.setEnabled(bool(m) and m["id"] not in self._carded)

    def _card_selected(self):
        m = self._selected()
        if m and add_card_from_mistake(self.win, m):
            self._reload()

    def _menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        m = self._rows[row]
        menu = QMenu(self)
        a_open = menu.addAction(T.icon("file-text", T.MUTED, 16), "Open practice")
        a_card = menu.addAction(T.icon("sparkles", T.RED, 16), "Add to flashcards")
        a_card.setEnabled(m["id"] not in self._carded)
        sub = menu.addMenu(T.icon("crosshair", T.MUTED, 16), "Set reason")
        picks = {}
        for key, name, icon, desc, _ in db.REASONS:
            a = sub.addAction(T.icon(icon, T.RED if key == m["reason"] else T.MUTED, 16), name)
            a.setToolTip(desc)
            picks[a] = key
        sub.addSeparator()
        picks[sub.addAction("No reason")] = ""
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen in picks:
            db.update_mistake(m["id"], "reason", picks[chosen])
            self.win.toast("Reason saved", 1000)
            self._reload()
            return
        if chosen is a_open:
            self._open(row, 0)
        elif chosen is a_card and add_card_from_mistake(self.win, m):
            self._reload()
