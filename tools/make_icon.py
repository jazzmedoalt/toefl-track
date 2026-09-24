"""Render the Nothing-style app icon: black squircle, 5×7 dot-matrix "T", one red dot.
Writes assets/icon.png (256), assets/icon-128.png and a multi-size assets/icon.ico. Run once."""
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

ROOT = Path(__file__).resolve().parent.parent

T_GLYPH = [
    "#####",
    "..#..",
    "..#..",
    "..#..",
    "..#..",
    "..#..",
    "..#..",
]


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 256
    p.setPen(QPen(QColor("#2A2A2A"), max(1.0, 3 * s)))
    p.setBrush(QColor("#000000"))
    p.drawRoundedRect(QRectF(2 * s, 2 * s, 252 * s, 252 * s), 60 * s, 60 * s)
    pitch = 24 * s
    ox = 128 * s - 2 * pitch
    oy = 128 * s - 3 * pitch + 4 * s
    p.setPen(Qt.NoPen)
    for r, row in enumerate(T_GLYPH):
        for c, ch in enumerate(row):
            on = ch == "#"
            p.setBrush(QColor("#FFFFFF" if on else "#262626"))
            p.drawEllipse(QPointF(ox + c * pitch, oy + r * pitch), (9.5 if on else 5.5) * s, (9.5 if on else 5.5) * s)
    p.setBrush(QColor("#D71921"))
    p.drawEllipse(QPointF(210 * s, 46 * s), 11 * s, 11 * s)
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    render(256).save(str(ROOT / "assets/icon.png"))
    render(128).save(str(ROOT / "assets/icon-128.png"))
    print("ico written:", render(256).save(str(ROOT / "assets/icon.ico")))
