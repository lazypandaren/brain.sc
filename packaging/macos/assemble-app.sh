#!/bin/bash
# Assemble Brain.app into a destination directory
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${1:?version}"
DEST="${2:?dest dir that will contain Brain.app}"
PKG="$ROOT/packaging/macos"

APP="$DEST/Brain.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

sed "s/__VERSION__/${VERSION}/g" "$PKG/Info.plist.in" > "$APP/Contents/Info.plist"
cp "$PKG/Brain-launcher.sh" "$APP/Contents/MacOS/Brain"
chmod 755 "$APP/Contents/MacOS/Brain"
cp "$PKG/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"

# Optional: PkgInfo
echo -n "APPL????" > "$APP/Contents/PkgInfo"

echo "Built $APP"
