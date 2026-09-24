"""Frameless dark dialogs: delete confirmation, new-flashcard form and paste import."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit,
                               QPlainTextEdit, QVBoxLayout)

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


class ImportDialog(_Panel):
    """Paste 'word:meaning' lines; live preview; copy an AI prompt that produces this format."""

    def __init__(self, parent, preview_fn, prompt, toast=None):
        super().__init__(parent)
        self._preview_fn = preview_fn
        self._prompt = prompt
        self._toast = toast
        self.setMinimumSize(600, 520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        lay.addWidget(label("Paste flashcards", "h2"))
        lay.addWidget(label("One card per line, the word, a colon, then its meaning.", "caption"))
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("car:vehicle you use to transport\nlie:you don't say the right thing")
        self.text.setAccessibleName("Cards to import, one word:meaning per line")
        self.text.setStyleSheet(f"font-family: '{T.MONO}'; font-size: 13px;")
        self.text.textChanged.connect(self._update)
        lay.addWidget(self.text, 1)
        self.preview = label("", "muted")
        self.preview.setWordWrap(True)
        lay.addWidget(self.preview)
        self.update_existing = QCheckBox("Update the meaning of words I already have")
        self.update_existing.toggled.connect(self._update)
        lay.addWidget(self.update_existing)

        ai = QVBoxLayout()
        ai.setSpacing(4)
        ai.addWidget(label("HAVE A PLAIN WORD LIST?", "eyebrow"))
        tip = label("Copy this prompt into ChatGPT, Claude or Gemini, add your words after it, and "
                    "paste the answer above.", "caption")
        tip.setWordWrap(True)
        ai.addWidget(tip)
        lay.addLayout(ai)

        row = QHBoxLayout()
        copy = self.copy_btn = button("Copy AI prompt", None, "copy")
        copy.clicked.connect(self._copy_prompt)
        row.addWidget(copy)
        row.addStretch(1)
        cancel = button("Cancel", "ghost")
        cancel.clicked.connect(self.reject)
        self.ok = button("Import", "primary", "download")
        self.ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.text.setFocus()
        self._update()

    def _update(self):
        msg, ready = self._preview_fn(self.text.toPlainText(), self.update_existing.isChecked())
        self.preview.setText(msg)
        self.ok.setEnabled(ready)

    def _copy_prompt(self):
        QApplication.clipboard().setText(self._prompt)
        if self._toast:
            self._toast("AI prompt copied. Paste it into your AI chat")

    def values(self):
        return self.text.toPlainText(), self.update_existing.isChecked()
