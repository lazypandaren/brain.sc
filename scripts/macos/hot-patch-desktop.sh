#!/bin/bash
# Hot-patch installed Brain desktop (close→tray) from this repo. Vault untouched.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/src/brain"
LIB="/usr/local/lib/brain-tools"
VENV_PY="$LIB/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  echo "Install not found: $VENV_PY" >&2
  exit 1
fi
# Resolve site-packages for whatever Python the venv uses (3.10+), not a hardcoded 3.12.
DST="$("$VENV_PY" -c 'import pathlib, sysconfig; print(pathlib.Path(sysconfig.get_path("purelib")) / "brain")')"
if [[ ! -d "$DST" ]]; then
  echo "Install not found: $DST" >&2
  exit 1
fi
echo "==> Patching $DST from $SRC"
cp "$SRC/desktop.py" "$SRC/desktop_ipc.py" "$SRC/ui_server.py" "$SRC/__init__.py" "$DST/"
rm -f "$DST"/__pycache__/desktop*.pyc "$DST"/__pycache__/desktop_ipc*.pyc \
  "$DST"/__pycache__/ui_server*.pyc "$DST"/__pycache__/__init__*.pyc 2>/dev/null || true
"$LIB/.venv/bin/brain" --version
echo "==> Done. Quit Brain (🧠 → Вийти) if running, then open Brain.app again."
