"""macOS LaunchAgent for Brain UI autostart at login."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from brain.errors import BrainError
from brain.service import ui_is_running, ui_port

LABEL = "com.braintools.ui"


def _agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def plist_path() -> Path:
    return _agents_dir() / f"{LABEL}.plist"


def _brain_bin() -> Path:
    for c in (
        Path("/usr/local/bin/brain"),
        Path.home() / "Library/Application Support/BrainTools/bin/brain",
    ):
        if c.is_file() and os.access(c, os.X_OK):
            return c
    which = shutil.which("brain")
    if which:
        return Path(which)
    raise BrainError("brain binary not found (install .pkg or put brain on PATH)")


def _log_dir() -> Path:
    d = Path.home() / "Library" / "Logs" / "BrainTools"
    d.mkdir(parents=True, exist_ok=True)
    return d


def render_plist(*, brain_bin: Path | None = None, port: int | None = None) -> str:
    bin_path = brain_bin or _brain_bin()
    port = port if port is not None else ui_port()
    logs = _log_dir()
    # Prefer desktop (window + tray). KeepAlive=false so close→tray doesn't respawn a second instance.
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{bin_path}</string>
    <string>desktop</string>
    <string>--port</string>
    <string>{port}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>ProcessType</key>
  <string>Interactive</string>
  <key>StandardOutPath</key>
  <string>{logs / "ui.stdout.log"}</string>
  <key>StandardErrorPath</key>
  <string>{logs / "ui.stderr.log"}</string>
</dict>
</plist>
"""


def is_enabled() -> bool:
    return plist_path().is_file()


def status() -> dict[str, object]:
    port = ui_port()
    try:
        bin_s = str(_brain_bin())
    except BrainError as e:
        bin_s = f"(missing: {e})"
    return {
        "label": LABEL,
        "plist": str(plist_path()),
        "enabled": is_enabled(),
        "ui_port": port,
        "ui_running": ui_is_running(port),
        "brain_bin": bin_s,
    }


def enable() -> Path:
    agents = _agents_dir()
    agents.mkdir(parents=True, exist_ok=True)
    path = plist_path()
    path.write_text(render_plist(), encoding="utf-8")
    # bootout if already loaded, then bootstrap
    uid = os.getuid()
    domain = f"gui/{uid}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(path)],
        check=False,
        capture_output=True,
    )
    proc = subprocess.run(
        ["launchctl", "bootstrap", domain, str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # Older macOS: load -w
        proc2 = subprocess.run(
            ["launchctl", "load", "-w", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc2.returncode != 0:
            raise BrainError(
                "launchctl failed: "
                + (proc.stderr or proc.stdout or proc2.stderr or proc2.stdout or "unknown")
            )
    return path


def disable() -> None:
    path = plist_path()
    uid = os.getuid()
    domain = f"gui/{uid}"
    if path.is_file():
        subprocess.run(
            ["launchctl", "bootout", domain, str(path)],
            check=False,
            capture_output=True,
        )
        subprocess.run(
            ["launchctl", "unload", "-w", str(path)],
            check=False,
            capture_output=True,
        )
        try:
            path.unlink()
        except OSError:
            pass
