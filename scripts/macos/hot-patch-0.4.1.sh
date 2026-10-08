#!/bin/bash
# Hot-patch installed Brain UI + desktop show-on-main (0.4.1). Vault untouched.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/../.." && pwd)"
LIB="/usr/local/lib/brain-tools"
SITE="$LIB/.venv/lib/python3.12/site-packages/brain"
if [[ ! -d "$SITE" ]]; then
  echo "Install not found: $SITE" >&2
  exit 1
fi
echo "==> Patching from $SRC"
cp "$SRC/ui/app.js" "$LIB/ui/app.js"
cp "$SRC/src/brain/desktop.py" "$SITE/desktop.py"
cp "$SRC/src/brain/ui_server.py" "$SITE/ui_server.py"
cp "$SRC/src/brain/__init__.py" "$SITE/__init__.py"
rm -f "$SITE"/__pycache__/desktop*.pyc "$SITE"/__pycache__/ui_server*.pyc \
  "$SITE"/__pycache__/__init__*.pyc 2>/dev/null || true
echo "==> Verify"
"$LIB/.venv/bin/brain" --version
grep -n 'includes("hub")' "$LIB/ui/app.js" | head -3
grep -n 'isMainThread' "$SITE/desktop.py" | head -3
grep -n '"hub": "hub" in tags' "$SITE/ui_server.py" || grep -n 'hub in tags' "$SITE/ui_server.py" | head -3
ls -la "$LIB/ui/app.js" "$SITE/desktop.py"
echo "==> Done. Quit Brain (🧠 → Quit) and reopen Brain.app"
