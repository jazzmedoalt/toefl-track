#!/usr/bin/env bash
# Build dist/TOEFL-Track-x86_64.AppImage (Linux). Needs: pyinstaller on PATH, curl.
# Usage: tools/build_appimage.sh [python-bin-dir]
set -euo pipefail
cd "$(dirname "$0")/.."
BIN="${1:-}"
PYI="${BIN:+$BIN/}pyinstaller"
OUT=build/appimage
APPDIR="$OUT/TOEFL-Track.AppDir"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' app/__init__.py)"

rm -rf "$OUT" && mkdir -p "$OUT"

# 1. PyInstaller folder build (no double extraction inside the AppImage)
TOEFL_ONEDIR=1 "$PYI" --noconfirm --clean --distpath "$OUT/dist" --workpath "$OUT/work" toefl_track.spec

# 2. AppDir layout
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -r "$OUT/dist/TOEFL-Track" "$APPDIR/usr/lib/toefl-track"
cp assets/icon.png "$APPDIR/toefl-track.png"
cp assets/icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/toefl-track.png"
cat > "$APPDIR/toefl-track.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TOEFL Track
Comment=Track TOEFL practice scores and mistakes
Exec=TOEFL-Track
Icon=toefl-track
Categories=Education;
Terminal=false
X-AppImage-Version=$VERSION
EOF
cp "$APPDIR/toefl-track.desktop" "$APPDIR/usr/share/applications/"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/toefl-track/TOEFL-Track" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# 3. Pack
TOOL="$OUT/appimagetool"
curl -fsSL -o "$TOOL" \
  https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "$TOOL"
mkdir -p dist
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" dist/TOEFL-Track-x86_64.AppImage
ls -la dist/TOEFL-Track-x86_64.AppImage
