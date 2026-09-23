"""Filesystem locations that work both from source and from a PyInstaller bundle."""
import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
ROOT = Path(__file__).resolve().parent.parent


def resource(rel: str) -> str:
    """Path to a bundled read-only asset (fonts, icons)."""
    base = Path(getattr(sys, "_MEIPASS", ROOT))
    return str(base / rel)


def _writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".toefl_write_test"
        probe.write_text("ok")
        probe.unlink()
        return True
    except OSError:
        return False


def data_dir() -> Path:
    """Portable: data lives next to the executable. Falls back to the user profile
    only if that folder is read-only (e.g. the exe was dropped in Program Files)."""
    here = Path(sys.executable).resolve().parent if FROZEN else ROOT
    if _writable(here):
        return here
    if os.name == "nt":
        fallback = Path(os.environ.get("APPDATA", Path.home())) / "TOEFL Track"
    else:
        fallback = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "toefl-track"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DB_PATH = data_dir() / "toefl_data.db"
