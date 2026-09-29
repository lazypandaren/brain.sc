#!/bin/bash
# Double-click / local install without .pkg (user home)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PREFIX="${BRAIN_INSTALL_PREFIX:-$HOME/Library/Application Support/BrainTools}"
BIN_DIR="${BRAIN_BIN_DIR:-$HOME/.local/bin}"

PYTHON=""
for c in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [[ -x "$c" ]] && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
    PYTHON="$c"
    break
  fi
done
[[ -n "$PYTHON" ]] || { echo "Need Python 3.10+"; exit 1; }

mkdir -p "$PREFIX" "$BIN_DIR"
rsync -a --delete \
  --exclude '.venv' --exclude 'dist' --exclude '.pytest_cache' \
  --exclude '**/__pycache__' --exclude '*.egg-info' --exclude '.git' \
  "$ROOT/" "$PREFIX/"

cd "$PREFIX"
rm -rf .venv
"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip -q
python -m pip install -e . -q

cat > "$BIN_DIR/brain" <<EOF
#!/bin/bash
export BRAIN_TOOLS_HOME="$PREFIX"
exec "$PREFIX/.venv/bin/brain" "\$@"
EOF
chmod 755 "$BIN_DIR/brain"

echo "Installed to: $PREFIX"
echo "Launcher: $BIN_DIR/brain"
if ! echo ":$PATH:" | grep -q ":$BIN_DIR:"; then
  echo "Add to PATH (zsh):  export PATH=\"$BIN_DIR:\$PATH\""
fi
brain --version || "$BIN_DIR/brain" --version
