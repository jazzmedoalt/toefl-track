"""Render assets/icon.png and assets/icon.ico (gradient tile + graduation cap). Run once."""
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor("#7C6BFF"))
    g.setColorAt(1, QColor("#2FB8DA"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    svg = (ROOT / "assets/icons/graduation-cap.svg").read_text().replace("currentColor", "#FFFFFF")
    m = size * 0.2
    QSvgRenderer(QByteArray(svg.encode())).render(p, QRectF(m, m, size - 2 * m, size - 2 * m))
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    render(256).save(str(ROOT / "assets/icon.png"))
    ok = render(256).save(str(ROOT / "assets/icon.ico"))
    print("ico written:", ok)
