#!/bin/bash
# Launcher for Brain.app — native window (pywebview), not Safari/Chrome.
#
# Critical: exec an interpreter *inside* this .app bundle so NSStatusItem /
# "Allow in the Menu Bar" is attributed to Brain (com.braintools.app), not
# a bare python3.12 process outside the bundle.
set -uo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
export BRAIN_TOOLS_HOME="${BRAIN_TOOLS_HOME:-/usr/local/lib/brain-tools}"
BRAIN_BIN="${BRAIN_TOOLS_HOME}/.venv/bin/brain"
# In-bundle Mach-O (copied at install / assemble). Fallback to venv python.
BUNDLE_PY="${DIR}/BrainPython"
VENV_PY="${BRAIN_TOOLS_HOME}/.venv/bin/python"
# Resolve purelib for the venv's Python (3.10+), not a hardcoded 3.12 path.
if [[ -x "$VENV_PY" ]]; then
  SITE="$("$VENV_PY" -c 'import sysconfig; print(sysconfig.get_path("purelib"))')"
else
  SITE=""
fi
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
  echo "bundle_py=${BUNDLE_PY} exists=$([[ -x "$BUNDLE_PY" ]] && echo yes || echo no)"
} >>"$LOG"

if [[ ! -x "$BRAIN_BIN" ]]; then
  alert "Brain CLI not found. Reinstall BrainTools.pkg."
  exit 1
fi

# Prefer in-bundle python so menu-bar extras belong to Brain.app
PY=()
if [[ -x "$BUNDLE_PY" ]]; then
  if [[ -n "${SITE}" ]]; then
    export PYTHONPATH="${SITE}${PYTHONPATH:+:$PYTHONPATH}"
  fi
  PY=("${RUN[@]}" "$BUNDLE_PY")
elif [[ -x "$VENV_PY" ]]; then
  PY=("${RUN[@]}" "$VENV_PY")
else
  alert "Brain Python not found. Reinstall BrainTools.pkg."
  exit 1
fi

if ! "${PY[@]}" -c "import brain" >>"$LOG" 2>&1; then
  alert "Brain failed to import. See ~/Library/Logs/BrainTools/ui.log"
  exit 1
fi

# Single-instance: if UI already up, desktop asks it to Show and exits 0
if "${PY[@]}" -c "import brain.desktop" >/dev/null 2>&1; then
  exec "${PY[@]}" -m brain desktop >>"$LOG" 2>&1
fi

# Legacy fallback
PORT="${BRAIN_UI_PORT:-8765}"
URL="http://127.0.0.1:${PORT}/"
if /usr/bin/curl -fsS --max-time 1 "$URL" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi
"${PY[@]}" -m brain ui --port "$PORT" >>"$LOG" 2>&1 &
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
