#!/bin/bash
# Remove BrainTools completely: processes, app, CLI, pkg receipt, logs, caches.
# Vault data (Markdown у твоїй папці/Google Drive) НЕ чіпається ніколи.
# Usage: bash uninstall.sh [--purge]   # --purge також видаляє ~/.config/brain
set -uo pipefail

PURGE=0
[[ "${1:-}" == "--purge" ]] && PURGE=1

echo "==> Stopping running Brain processes"
pkill -f "/usr/local/lib/brain-tools/.venv" 2>/dev/null || true
pkill -f "Brain.app/Contents/MacOS/Brain" 2>/dev/null || true
pkill -f "python[0-9.]* -m brain" 2>/dev/null || true
sleep 1
pkill -9 -f "/usr/local/lib/brain-tools/.venv" 2>/dev/null || true

echo "==> Disabling LaunchAgent autostart (if any)"
UID_NUM="$(id -u)"
PLIST="$HOME/Library/LaunchAgents/com.braintools.ui.plist"
launchctl bootout "gui/${UID_NUM}" "$PLIST" 2>/dev/null || true
launchctl unload -w "$PLIST" 2>/dev/null || true
rm -f "$PLIST" 2>/dev/null || true

echo "==> Removing installed files (sudo)"
sudo rm -f /usr/local/bin/brain
sudo rm -rf /usr/local/lib/brain-tools
sudo rm -rf /Applications/Brain.app
sudo pkgutil --forget com.braintools.cli 2>/dev/null || true

echo "==> Removing logs and caches"
rm -rf "$HOME/Library/Logs/BrainTools" 2>/dev/null || true
sudo rm -rf /tmp/braintools-install.log /tmp/braintools-pip-cache 2>/dev/null || true

if [[ "$PURGE" -eq 1 ]]; then
  echo "==> Purging user config ~/.config/brain"
  rm -rf "$HOME/.config/brain"
else
  echo "Config kept: ~/.config/brain (re-run with --purge to delete it too)."
fi

if pgrep -f "brain-tools|Brain.app" >/dev/null 2>&1; then
  echo "WARN: some Brain processes are still alive:"
  pgrep -fl "brain-tools|Brain.app" || true
else
  echo "OK: no Brain processes running."
fi
echo "Done. Vault (Markdown data) untouched."
