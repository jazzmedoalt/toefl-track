"""Frameless dark dialogs: delete confirmation and new-flashcard form."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLineEdit, QVBoxLayout

from .. import theme as T
from .cards import button, label


class _Panel(QDialog):
    """Frameless rounded dark panel used by the app's dialogs."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(T.BORDER_HI), 1))
        p.setBrush(QColor(T.SURFACE))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)


class ConfirmDialog(_Panel):
    def __init__(self, parent, title, text, confirm_text="Delete"):
        super().__init__(parent)
        self.setMinimumWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(8)
        lay.addWidget(label(title, "h2"))
        body = label(text, "muted")
        body.setWordWrap(True)
        lay.addWidget(body)
        lay.addSpacing(12)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = button("Cancel", "ghost")
        ok = button(confirm_text)
        ok.setStyleSheet(f"QPushButton {{ background: #B42318; border-color: #D92D20; color: white; }}"
                         f"QPushButton:hover {{ background: #D92D20; }}"
                         f"QPushButton:focus {{ border-color: {T.TEXT}; }}")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        cancel.setFocus()


def confirm(parent, title, text, confirm_text="Delete") -> bool:
    return ConfirmDialog(parent, title, text, confirm_text).exec() == QDialog.Accepted


class CardDialog(_Panel):
    """Create a flashcard, optionally prefilled from a mistake."""
    FIELDS = (("word", "Word"), ("meaning", "Meaning"), ("example", "Example sentence"),
              ("synonyms", "Synonyms"))

    def __init__(self, parent, prefill=None, title="New flashcard"):
        super().__init__(parent)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(8)
        lay.addWidget(label(title, "h2"))
        lay.addWidget(label("Front: the word. Back: its meaning, an example and synonyms.", "caption"))
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.inputs = {}
        for key, name in self.FIELDS:
            e = QLineEdit((prefill or {}).get(key, ""))
            e.setAccessibleName(name)
            e.returnPressed.connect(self._save)
            self.inputs[key] = e
            form.addRow(label(name, "muted"), e)
        lay.addLayout(form)
        lay.addSpacing(8)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = button("Cancel", "ghost")
        save = button("Add card", "primary", "plus")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(save)
        lay.addLayout(row)
        target = self.inputs["meaning"] if self.inputs["word"].text() else self.inputs["word"]
        target.setFocus()
        target.selectAll()

    def _save(self):
        if not self.inputs["word"].text().strip():
            self.inputs["word"].setFocus()
            return
        self.accept()

    def values(self):
        return {k: e.text().strip() for k, e in self.inputs.items()}


def ask_card(parent, prefill=None):
    d = CardDialog(parent, prefill)
    return d.values() if d.exec() == QDialog.Accepted else None
