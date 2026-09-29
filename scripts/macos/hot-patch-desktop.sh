#!/bin/bash
# Hot-patch installed Brain desktop (close→tray) from this repo. Vault untouched.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/src/brain"
DST="/usr/local/lib/brain-tools/.venv/lib/python3.12/site-packages/brain"
if [[ ! -d "$DST" ]]; then
  echo "Install not found: $DST" >&2
  exit 1
fi
echo "==> Patching $DST from $SRC"
cp "$SRC/desktop.py" "$SRC/desktop_ipc.py" "$SRC/ui_server.py" "$SRC/__init__.py" "$DST/"
rm -f "$DST"/__pycache__/desktop*.pyc "$DST"/__pycache__/desktop_ipc*.pyc \
  "$DST"/__pycache__/ui_server*.pyc "$DST"/__pycache__/__init__*.pyc 2>/dev/null || true
"/usr/local/lib/brain-tools/.venv/bin/brain" --version
echo "==> Done. Quit Brain (🧠 → Вийти) if running, then open Brain.app again."
