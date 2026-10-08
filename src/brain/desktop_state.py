"""Shared desktop process state (tray / show / quit).

Kept separate from Cocoa helpers so `desktop.py` stays orchestration-only.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

allow_quit = False
keepalive_ref = None
tray_refs: list[Any] = []
tray_status = None
main_window = None
TrayDelegateCls = None


def log_path() -> Path:
    return Path.home() / "Library" / "Logs" / "BrainTools" / "desktop.log"


def desk_log(msg: str) -> None:
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")
    except Exception:
        pass
