# TOEFL Track

A small, dark desktop app for tracking TOEFL practice.

**Set → Practice → score out of 10 → mistakes** (the wrong answer, the correct one, the mistake type and the topic).

- **Dashboard:** practice count, average, best score, animated score trend, top mistake types, recent practices.
- **Sets:** one card per set with its average and a sparkline. Open a set to see its practices.
- **Practice editor:** pick the score from 0 to 10 by clicking or by typing a digit. Type a mistake and press **Enter** to add it, and double-click a cell to edit it. Everything saves automatically.
- **Mistakes:** every wrong answer in one searchable list, filtered by type or set. Double-click a row to open its practice.
- **Settings:** open the data folder, export to CSV, and turn motion down.

## Portable

Everything is stored in `toefl_data.db`, **next to the app file**. To move your progress to another computer, copy the app and that file. If the app's folder is read-only, the data goes to `%APPDATA%\TOEFL Track` on Windows or `~/.local/share/toefl-track` on Linux.

## Get the .exe

Every push to GitHub builds the app on GitHub Actions, for both Windows and Linux:

1. Push this folder to a GitHub repository.
2. Open **Actions → Build portable app → the latest run → Artifacts**.
3. Download **TOEFL-Track.exe** (Windows), **TOEFL-Track-x86_64.AppImage** (Linux, recommended: it shows the app icon and needs no install), or the plain **TOEFL-Track** Linux binary. On Linux, run `chmod +x` on the file first.

The AppImage keeps `toefl_data.db` next to the `.AppImage` file. To build it locally, run `tools/build_appimage.sh .venv/bin`.

To publish a release, push a tag: `git tag v1.0.0 && git push --tags`. Both files are then attached to a GitHub Release.

## Run from source

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
.venv/bin/python run.py
```

Build locally (the build runs on the same OS it's building for):

```bash
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --noconfirm --clean toefl_track.spec   # → dist/
```

## Credits

- UI: PySide6 (Qt 6)
- Font: [Inter](https://rsms.me/inter/) (SIL OFL)
- Icons: [Lucide](https://lucide.dev) (ISC)
