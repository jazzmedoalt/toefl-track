#!/usr/bin/env bash
# Build dist/TOEFL-Track-x86_64.AppImage (+ .zsync) on Linux. Needs: pyinstaller on PATH, curl,
# and appstreamcli (package "appstream") for metadata validation.
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

# 2. AppDir layout (desktop file, AppStream metainfo and icons are what Gear Lever reads)
ID=io.github.jazzmedoalt.toefltrack
REPO=https://github.com/jazzmedoalt/toefl-track
RAW=https://raw.githubusercontent.com/jazzmedoalt/toefl-track/main/docs/screenshots
mkdir -p "$APPDIR/usr/lib" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/metainfo" \
  "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/icons/hicolor/128x128/apps"
cp -r "$OUT/dist/TOEFL-Track" "$APPDIR/usr/lib/toefl-track"
cp assets/icon.png "$APPDIR/$ID.png"
cp assets/icon.png "$APPDIR/.DirIcon"
cp assets/icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/$ID.png"
cp assets/icon-128.png "$APPDIR/usr/share/icons/hicolor/128x128/apps/$ID.png"
cat > "$APPDIR/$ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TOEFL Track
GenericName=TOEFL Tracker
Comment=Track TOEFL practice scores, mistakes and flashcards
Exec=TOEFL-Track
Icon=$ID
Categories=Education;Languages;
Keywords=TOEFL;English;study;flashcards;vocabulary;exam;
StartupWMClass=TOEFL-Track
Terminal=false
X-AppImage-Version=$VERSION
EOF
cp "$APPDIR/$ID.desktop" "$APPDIR/usr/share/applications/"
cat > "$APPDIR/usr/share/metainfo/$ID.appdata.xml" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>$ID</id>
  <name>TOEFL Track</name>
  <summary>Track TOEFL practice scores, mistakes and flashcards</summary>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>MIT</project_license>
  <developer id="io.github.jazzmedoalt">
    <name>jazzmedoalt</name>
  </developer>
  <description>
    <p>A small, offline study tracker for the TOEFL with a black, white and red dot-matrix look.</p>
    <ul>
      <li>Organise practice into sets and log each score out of 10</li>
      <li>Record every wrong answer with the correct one and its mistake type</li>
      <li>See your trend, streak and a score calendar by week or month</li>
      <li>Learn words with spaced-repetition flashcards, or paste a word:meaning list</li>
      <li>Quiz yourself on your own past mistakes</li>
      <li>Everything is saved in one file next to the app</li>
    </ul>
  </description>
  <launchable type="desktop-id">$ID.desktop</launchable>
  <url type="homepage">$REPO</url>
  <url type="bugtracker">$REPO/issues</url>
  <categories>
    <category>Education</category>
  </categories>
  <content_rating type="oars-1.1"/>
  <screenshots>
    <screenshot type="default">
      <caption>Dashboard</caption>
      <image>$RAW/dashboard.png</image>
    </screenshot>
    <screenshot>
      <caption>Score calendar</caption>
      <image>$RAW/calendar.png</image>
    </screenshot>
    <screenshot>
      <caption>Flashcards</caption>
      <image>$RAW/flashcards.png</image>
    </screenshot>
    <screenshot>
      <caption>Practice editor</caption>
      <image>$RAW/practice.png</image>
    </screenshot>
  </screenshots>
  <releases>
    <release version="1.2.0" date="2026-09-24">
      <description><p>Nothing OS inspired redesign, score calendar, paste flashcards as word:meaning lines, new icon.</p></description>
    </release>
    <release version="1.1.0" date="2026-09-24">
      <description><p>Flashcards, quiz from mistakes, exam countdown and study streak.</p></description>
    </release>
    <release version="1.0.1" date="2026-09-23"/>
    <release version="1.0.0" date="2026-09-23"/>
  </releases>
</component>
EOF
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/toefl-track/TOEFL-Track" "$@"
EOF
chmod +x "$APPDIR/AppRun"

# validate metadata offline (screenshot URLs are only reachable once pushed)
appstreamcli validate --no-net --explain "$APPDIR/usr/share/metainfo/$ID.appdata.xml"
desktop-file-validate "$APPDIR/$ID.desktop" 2>/dev/null || true

# 3. Pack, with update info so Gear Lever / AppImageUpdate can fetch new releases
TOOL="$OUT/appimagetool"
curl -fsSL -o "$TOOL" \
  https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "$TOOL"
mkdir -p dist
rm -f dist/TOEFL-Track-x86_64.AppImage dist/TOEFL-Track-x86_64.AppImage.zsync
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" \
  --no-appstream -u "gh-releases-zsync|jazzmedoalt|toefl-track|latest|TOEFL-Track-*x86_64.AppImage.zsync" \
  "$APPDIR" dist/TOEFL-Track-x86_64.AppImage
[ -f TOEFL-Track-x86_64.AppImage.zsync ] && mv TOEFL-Track-x86_64.AppImage.zsync dist/
ls -la dist/TOEFL-Track-x86_64.AppImage*
