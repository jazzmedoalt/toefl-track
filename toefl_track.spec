# PyInstaller spec: one portable file (TOEFL-Track.exe on Windows, TOEFL-Track on Linux).
# Build:  pyinstaller --noconfirm --clean toefl_track.spec
import sys

# Only QtCore/QtGui/QtWidgets/QtSvg are used; drop the rest to keep the file small.
EXCLUDES = [
    "tkinter", "unittest", "pydoc", "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.QtQuickWidgets", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtMultimedia", "PySide6.QtWebEngineCore", "PySide6.QtDBus",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtXml", "PySide6.QtConcurrent", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtPrintSupport", "PySide6.QtUiTools", "PySide6.QtSvgWidgets",
]

a = Analysis(
    ["run.py"],
    pathex=[],
    datas=[("assets", "assets")],
    hiddenimports=["PySide6.QtSvg"],
    excludes=EXCLUDES,
    noarchive=False,
)

# Strip Qt translations and unused plugins that PyInstaller's hook pulls in. The GTK platform
# theme is dropped on purpose: the app draws its own dark theme and never follows the OS.
DROP = ("translations", "qtwebengine", "Qt6Quick", "Qt6Qml", "Qt6Pdf", "Qt6Network",
        "Qt6VirtualKeyboard", "opengl32sw", "Qt6Multimedia", "platformthemes",
        "libgtk-3", "libgdk-3", "libgdk_pixbuf", "libglycin", "libcairo", "libpango", "libatk",
        "libepoxy", "librsvg")
a.datas = [d for d in a.datas if not any(x in d[0] for x in DROP)]
a.binaries = [b for b in a.binaries if not any(x in b[0] for x in DROP)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TOEFL-Track",
    debug=False,
    strip=sys.platform != "win32",
    upx=False,  # UPX-packed exes trigger antivirus false positives on Windows
    runtime_tmpdir=None,
    console=False,
    icon="assets/icon.ico" if sys.platform == "win32" else None,
)
