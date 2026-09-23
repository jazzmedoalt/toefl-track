"""Small frameless confirmation dialog that matches the dark theme."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QVBoxLayout

from .. import theme as T
from .cards import button, label


class ConfirmDialog(QDialog):
    def __init__(self, parent, title, text, confirm_text="Delete"):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
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

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(T.BORDER_HI), 1))
        p.setBrush(QColor(T.SURFACE))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)


def confirm(parent, title, text, confirm_text="Delete") -> bool:
    return ConfirmDialog(parent, title, text, confirm_text).exec() == QDialog.Accepted
