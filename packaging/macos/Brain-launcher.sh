#!/bin/bash
# Launcher for Brain.app — native window (pywebview), not Safari/Chrome
set -uo pipefail

export BRAIN_TOOLS_HOME="${BRAIN_TOOLS_HOME:-/usr/local/lib/brain-tools}"
BRAIN_BIN="${BRAIN_TOOLS_HOME}/.venv/bin/brain"
LOG_DIR="${HOME}/Library/Logs/BrainTools"
LOG="${LOG_DIR}/ui.log"
mkdir -p "$LOG_DIR"

RUN=()
if /usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null | grep -q 1; then
  RUN=(/usr/bin/arch -arm64)
fi

alert() {
  /usr/bin/osascript -e "display alert \"Brain\" message \"$1\" as critical" >/dev/null 2>&1 || true
}

{
  echo "---- $(date) ----"
  echo "uname=$(uname -m) translated=$(/usr/sbin/sysctl -n sysctl.proc_translated 2>/dev/null || echo n/a)"
  echo "mode=desktop"
} >>"$LOG"

if [[ ! -x "$BRAIN_BIN" ]]; then
  alert "Brain CLI not found. Reinstall BrainTools.pkg."
  exit 1
fi

if ! "${RUN[@]}" "$BRAIN_BIN" --version >>"$LOG" 2>&1; then
  alert "Brain failed to start. See ~/Library/Logs/BrainTools/ui.log"
  exit 1
fi

# Prefer native desktop window; fallback to ui+browser only if desktop cmd missing
if "${RUN[@]}" "$BRAIN_BIN" desktop --help >/dev/null 2>&1; then
  # Single-instance: if UI already up, `brain desktop` asks it to Show and exits 0
  exec "${RUN[@]}" "$BRAIN_BIN" desktop >>"$LOG" 2>&1
fi

# Legacy fallback
PORT="${BRAIN_UI_PORT:-8765}"
URL="http://127.0.0.1:${PORT}/"
if /usr/bin/curl -fsS --max-time 1 "$URL" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi
"${RUN[@]}" "$BRAIN_BIN" ui --port "$PORT" >>"$LOG" 2>&1 &
UI_PID=$!
for _ in $(seq 1 50); do
  if /usr/bin/curl -fsS --max-time 1 "$URL" >/dev/null 2>&1; then
    open "$URL"
    wait "$UI_PID" || true
    exit 0
  fi
  if ! kill -0 "$UI_PID" 2>/dev/null; then
    alert "Failed to start Brain UI. See ~/Library/Logs/BrainTools/ui.log"
    exit 1
  fi
  sleep 0.2
done
alert "Brain UI did not start in time."
exit 1
