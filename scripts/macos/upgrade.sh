#!/bin/bash
# In-place upgrade: install a new .pkg over the existing BrainTools install.
# Does NOT uninstall, does NOT touch vault or ~/.config/brain.
# Usage: ./scripts/macos/upgrade.sh [path/to/BrainTools-….pkg]
set -euo pipefail

PKG="${1:-}"
if [[ -z "$PKG" ]]; then
  if command -v brain >/dev/null 2>&1; then
    exec brain upgrade
  fi
  echo "Usage: $0 /path/to/BrainTools-<ver>-<arch>.pkg" >&2
  exit 2
fi

PKG="$(cd "$(dirname "$PKG")" && pwd)/$(basename "$PKG")"
if [[ ! -f "$PKG" ]]; then
  echo "Not found: $PKG" >&2
  exit 1
fi

echo "==> Upgrading BrainTools from $PKG (vault preserved)"
sudo xattr -dr com.apple.quarantine "$PKG" 2>/dev/null || true
sudo installer -pkg "$PKG" -target /
echo "==> Done. Restart Brain.app or: brain ui"
if command -v brain >/dev/null 2>&1; then
  brain --version || true
  brain agents install --all 2>/dev/null || true
fi
