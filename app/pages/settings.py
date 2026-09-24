from datetime import date

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDateEdit, QFileDialog, QHBoxLayout, QVBoxLayout

from .. import __version__, db
from .. import theme as T
from ..paths import DB_PATH
from ..widgets.cards import Card, ScorePicker, Toggle, button, label
from .base import Page


class SettingsPage(Page):
    def __init__(self, win):
        super().__init__(win, "Settings", "Your exam, your data, and how the app behaves")

        ex = Card()
        ex.layout().addWidget(label("Exam", "h2"))
        ex.layout().addWidget(label("Set your test date and the practice average you're aiming for. "
                                    "The dashboard shows a countdown and whether you're on track.", "caption"))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(label("Test date", "muted"))
        self.exam_date = QDateEdit()
        self.exam_date.setCalendarPopup(True)
        self.exam_date.setDisplayFormat("d MMM yyyy")
        self.exam_date.setAccessibleName("Exam date")
        self.exam_date.setMinimumWidth(150)
        row.addWidget(self.exam_date)
        self.set_btn = button("Set", "primary", "check")
        self.set_btn.clicked.connect(lambda: self._save_exam_date(self.exam_date.date()))
        row.addWidget(self.set_btn)
        self.clear_exam = button("Clear", "ghost")
        self.clear_exam.clicked.connect(self._clear_exam)
        row.addWidget(self.clear_exam)
        row.addStretch(1)
        ex.layout().addLayout(row)
        ex.layout().addWidget(label("Target practice average (out of 10)", "muted"))
        self.target = ScorePicker()
        self.target.setAccessibleName("Target average")
        ex.layout().addWidget(self.target)
        self.body.addWidget(ex)
        self._load_exam()
        self.exam_date.dateChanged.connect(self._save_exam_date)
        self.target.valueChanged.connect(self._save_target)

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
            f"TOEFL Track {__version__}. Log sets, practices, scores and mistakes, learn words with "
            "flashcards, quiz yourself, and watch your progress.\nFont: Inter (SIL OFL). Icons: Lucide (ISC).", "caption"))
        self.body.addWidget(about)
        self.body.addStretch(1)

    def _load_exam(self):
        raw = db.get_setting("exam_date")
        self.exam_date.blockSignals(True)
        self.exam_date.setDate(QDate.fromString(raw, "yyyy-MM-dd") if raw else QDate.currentDate().addMonths(1))
        self.exam_date.blockSignals(False)
        self.clear_exam.setVisible(bool(raw))
        self.set_btn.setVisible(not raw)
        self.target.setValue(int(db.get_setting("target_avg", "8")), animate=False)

    def refresh(self):
        self._load_exam()

    def _save_exam_date(self, d):
        db.set_setting("exam_date", d.toString("yyyy-MM-dd"))
        self.clear_exam.show()
        self.set_btn.hide()
        self.win.toast("Exam date saved")

    def _clear_exam(self):
        db.set_setting("exam_date", "")
        self.clear_exam.hide()
        self.set_btn.show()
        self.win.toast("Exam date cleared")

    def _save_target(self, v):
        db.set_setting("target_avg", v)
        self.win.toast(f"Target: {v}/10")

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
