"""Wrong-answer reason pickers: a combo box (icon + name, description as tooltip) and a table delegate."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate

from .. import db
from .. import theme as T

KEY_ROLE = Qt.UserRole + 1     # table items keep the reason key here; the cell shows its name


def reason_combo(blank="No reason", parent=None) -> QComboBox:
    cb = QComboBox(parent)
    cb.setAccessibleName("Reason")
    cb.setToolTip("Why did the wrong answer fool you?")
    cb.addItem(blank, "")
    for r in db.REASONS:
        key, name, icon, desc, _ = r
        cb.addItem(T.icon(icon, T.MUTED, 16), name, key)
        cb.setItemData(cb.count() - 1, desc, Qt.ToolTipRole)
    return cb


def set_reason(cb: QComboBox, key):
    cb.setCurrentIndex(max(0, cb.findData(key or "")))


class ReasonDelegate(QStyledItemDelegate):
    """Edits a reason cell with the combo; stores the key in KEY_ROLE and shows the name."""

    def createEditor(self, parent, option, index):
        cb = reason_combo(parent=parent)
        cb.activated.connect(lambda _=0, cb=cb: (self.commitData.emit(cb), self.closeEditor.emit(cb)))
        return cb

    def setEditorData(self, editor, index):
        set_reason(editor, index.data(KEY_ROLE))
        editor.showPopup()

    def setModelData(self, editor, model, index):
        key = editor.currentData() or ""
        model.setData(index, key, KEY_ROLE)
        model.setData(index, db.reason_name(key), Qt.DisplayRole)
        r = db.REASON.get(key)
        model.setData(index, T.icon(r["icon"], T.MUTED, 16) if r else None, Qt.DecorationRole)
