#!/bin/bash
# Version-agnostic hot-patch of installed Brain UI + desktop from this repo.
# Vault untouched. Resolves site-packages via the venv's Python (3.10+).
set -euo pipefail
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
LIB="${BRAIN_TOOLS_HOME:-/usr/local/lib/brain-tools}"
VENV_PY="$LIB/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Install not found: $VENV_PY" >&2
  exit 1
fi
SITE="$("$VENV_PY" -c 'import pathlib, sysconfig; print(pathlib.Path(sysconfig.get_path("purelib")) / "brain")')"
if [[ ! -d "$SITE" ]]; then
  echo "Install not found: $SITE" >&2
  exit 1
fi
echo "==> Patching from $SRC"
echo "    site-packages: $SITE"
# UI
if [[ -f "$SRC/ui/app.js" && -d "$LIB/ui" ]]; then
  cp "$SRC/ui/app.js" "$LIB/ui/app.js"
  [[ -f "$SRC/ui/index.html" ]] && cp "$SRC/ui/index.html" "$LIB/ui/index.html"
  [[ -f "$SRC/ui/style.css" ]] && cp "$SRC/ui/style.css" "$LIB/ui/style.css"
fi
# Python package (desktop split + hubs)
for f in desktop.py desktop_cocoa.py desktop_state.py desktop_ipc.py ui_server.py hubs.py __init__.py agents_install.py; do
  if [[ -f "$SRC/src/brain/$f" ]]; then
    cp "$SRC/src/brain/$f" "$SITE/$f"
  fi
done
rm -f "$SITE"/__pycache__/*.pyc 2>/dev/null || true
echo "==> Verify"
"$LIB/.venv/bin/brain" --version
ls -la "$SITE/desktop.py" "$SITE/hubs.py" 2>/dev/null || true
echo "==> Done. Quit Brain and reopen Brain.app"
