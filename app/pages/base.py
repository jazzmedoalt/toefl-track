"""Shared page scaffold: header (title, subtitle, actions) above a scrolling or fixed body."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import db
from ..widgets.cards import label
from ..widgets.dialog import ask_card

MARGIN = 28


class Page(QWidget):
    def __init__(self, win, title="", subtitle="", scroll=True, parent=None):
        super().__init__(parent)
        self.win = win
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QWidget()
        self.header = QHBoxLayout(head)
        self.header.setContentsMargins(MARGIN, 18, MARGIN, 14)
        self.header.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.title = label(title, "h1")
        self.subtitle = label(subtitle, "muted")
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        self.header.addLayout(titles, 1)
        outer.addWidget(head)

        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(MARGIN, 4, MARGIN, MARGIN)
        self.body.setSpacing(14)
        if scroll:
            area = QScrollArea()
            area.setWidgetResizable(True)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(content)
            outer.addWidget(area, 1)
        else:
            outer.addWidget(content, 1)

    def add_action(self, w):
        self.header.addWidget(w, 0, Qt.AlignVCenter)
        return w

    def refresh(self):
        pass


def clear_layout(lay):
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


def add_card_from_mistake(win, m) -> bool:
    """Open the card dialog prefilled from a mistake; returns True if a card was created."""
    v = ask_card(win, {"word": m["correct"] or m["wrong"],
                       "meaning": f"Not: {m['wrong']}" if m["wrong"] and m["correct"] else ""})
    if not v:
        return False
    db.add_card(**v, mistake_id=m["id"])
    win.toast(f"Added “{v['word']}” to flashcards")
    return True
