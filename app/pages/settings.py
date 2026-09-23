from datetime import date

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout

from .. import __version__, db
from .. import theme as T
from ..paths import DB_PATH
from ..widgets.cards import Card, Toggle, button, label
from .base import Page


class SettingsPage(Page):
    def __init__(self, win):
        super().__init__(win, "Settings", "Your data, and how the app behaves")

        data = Card()
        data.layout().addWidget(label("Your data", "h2"))
        data.layout().addWidget(label("Everything is stored in one file next to the app. Copy the app "
                                      "together with this file and your progress goes with it.", "caption"))
        path = label(str(DB_PATH))
        path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path.setStyleSheet(f"background: {T.RAISED}; border: 1px solid {T.BORDER}; border-radius: 8px;"
                           f" padding: 8px 10px; font-family: monospace; color: {T.MUTED};")
        path.setWordWrap(True)
        data.layout().addWidget(path)
        row = QHBoxLayout()
        open_btn = button("Open folder", None, "folder-open")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DB_PATH.parent))))
        export_btn = button("Export to CSV", None, "download")
        export_btn.clicked.connect(self._export)
        row.addWidget(open_btn)
        row.addWidget(export_btn)
        row.addStretch(1)
        data.layout().addLayout(row)
        self.body.addWidget(data)

        motion = Card()
        row = QHBoxLayout()
        txt = QVBoxLayout()
        txt.setSpacing(2)
        txt.addWidget(label("Reduce motion", "h2"))
        txt.addWidget(label("Turn off page transitions and chart animations.", "caption"))
        row.addLayout(txt, 1)
        self.reduce = Toggle()
        self.reduce.setAccessibleName("Reduce motion")
        self.reduce.setChecked(db.get_setting("reduce_motion", "0") == "1")
        self.reduce.toggled.connect(self._toggle_motion)
        row.addWidget(self.reduce)
        motion.layout().addLayout(row)
        self.body.addWidget(motion)

        about = Card()
        about.layout().addWidget(label("About", "h2"))
        about.layout().addWidget(label(
            f"TOEFL Track {__version__}. Log sets, practices, scores and mistakes, and watch "
            "your progress.\nFont: Inter (SIL OFL). Icons: Lucide (ISC).", "caption"))
        self.body.addWidget(about)
        self.body.addStretch(1)

    def _toggle_motion(self, on):
        db.set_setting("reduce_motion", "1" if on else "0")
        T.MOTION["enabled"] = not on
        self.win.toast("Motion reduced" if on else "Animations on")

    def _export(self):
        default = str(DB_PATH.parent / f"toefl_progress_{date.today().isoformat()}.csv")
        path, _ = QFileDialog.getSaveFileName(self, "Export to CSV", default, "CSV files (*.csv)")
        if path:
            n = db.export_csv(path)
            self.win.toast(f"Exported {n} rows")
