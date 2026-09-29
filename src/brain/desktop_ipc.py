"""Cross-thread IPC: UI server ↔ desktop window (show-from-tray / second launch)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from brain.paths import user_config_dir

_show = threading.Event()
_last_file_mtime = 0.0


def show_request_path() -> Path:
    return user_config_dir() / "desktop.show"


def request_show() -> None:
    """Ask the running desktop process to bring the window forward."""
    _show.set()
    try:
        path = show_request_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


def clear_show() -> None:
    global _last_file_mtime
    _show.clear()
    try:
        path = show_request_path()
        if path.is_file():
            _last_file_mtime = path.stat().st_mtime
            path.unlink(missing_ok=True)
    except OSError:
        pass


def wait_show(timeout: float = 0.6) -> bool:
    """True if show was requested via Event (same process) or desktop.show file (handoff)."""
    global _last_file_mtime
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _show.is_set():
            clear_show()
            return True
        try:
            path = show_request_path()
            if path.is_file():
                mtime = path.stat().st_mtime
                if mtime > _last_file_mtime:
                    _last_file_mtime = mtime
                    clear_show()
                    return True
        except OSError:
            pass
        time.sleep(0.1)
    return False
