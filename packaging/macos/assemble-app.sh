#!/bin/bash
# Assemble Brain.app into a destination directory
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${1:?version}"
DEST="${2:?dest dir that will contain Brain.app}"
PKG="$ROOT/packaging/macos"
# Optional override when assembling against an installed tree
BRAIN_TOOLS_HOME="${BRAIN_TOOLS_HOME:-/usr/local/lib/brain-tools}"
RUNTIME_PY="${BRAIN_TOOLS_HOME}/runtime/python/bin/python3.12"
RUNTIME_LIB="${BRAIN_TOOLS_HOME}/runtime/python/lib"

APP="$DEST/Brain.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

sed "s/__VERSION__/${VERSION}/g" "$PKG/Info.plist.in" > "$APP/Contents/Info.plist"
cp "$PKG/Brain-launcher.sh" "$APP/Contents/MacOS/Brain"
chmod 755 "$APP/Contents/MacOS/Brain"
cp "$PKG/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"

# In-bundle Mach-O interpreter (NOT a symlink to outside) so menu-bar extras
# attribute to com.braintools.app. RPATH is @executable_path/../lib → Contents/lib.
if [[ -f "$RUNTIME_PY" ]]; then
  cp "$RUNTIME_PY" "$APP/Contents/MacOS/BrainPython"
  chmod 755 "$APP/Contents/MacOS/BrainPython"
  ln -sfn "$RUNTIME_LIB" "$APP/Contents/lib"
else
  echo "warn: $RUNTIME_PY missing — Brain.app will fall back to venv python (menu bar may show python3.12)" >&2
fi

# Optional: PkgInfo
echo -n "APPL????" > "$APP/Contents/PkgInfo"

echo "Built $APP"
