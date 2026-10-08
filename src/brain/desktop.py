"""Native desktop window (pywebview) + macOS menu-bar tray (close → tray).

Stability:
- Single instance: if Brain already listens on the UI port, ask it to Show and exit.
- Closing the window hides to tray/Dock — does not quit the process.
- Cocoa patches live in `desktop_cocoa.py` (AppKit / pywebview delegates).
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

from brain import desktop_state as state
from brain.config import load_user_config, resolve_root
from brain.desktop_ipc import clear_show, request_show, wait_show
from brain.errors import BrainError
from brain.ui_server import run_ui

# Back-compat aliases used by tests / older hot-patches
_desk_log = state.desk_log
_allow_quit = state.allow_quit  # noqa: F841 — mirrored; prefer state.allow_quit


def _probe_brain(port: int) -> dict | None:
    url = f"http://127.0.0.1:{port}/api/status"
    try:
        with urllib.request.urlopen(url, timeout=0.6) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("ui_running") or data.get("version"):
        return data
    return None


def _post_show(port: int) -> bool:
    """Ask running instance to show via HTTP (preferred) + file flag."""
    request_show()
    url = f"http://127.0.0.1:{port}/api/desktop/show"
    try:
        req = urllib.request.Request(
            url,
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            ok = resp.status == 200
            state.desk_log(f"requested show on existing instance port={port} http={ok}")
            return ok
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        state.desk_log(f"show HTTP failed (file flag still set): {e}")
        return _probe_brain(port) is not None


def _request_existing_show(port: int) -> bool:
    if _probe_brain(port) is None:
        return False
    return _post_show(port)


def _wait_ready(port: int, timeout: float = 8.0) -> None:
    url = f"http://127.0.0.1:{port}/api/status"
    deadline = time.time() + timeout
    last: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.15)
    raise BrainError(f"UI server did not start on port {port}: {last}")


def _show_window(window=None) -> None:
    """Bring Brain window forward — must run on AppKit main thread (macOS)."""
    window = window or state.main_window
    if window is None:
        state.desk_log("show skipped: no window ref")
        return

    def _do() -> None:
        try:
            window.show()
        except Exception:
            pass
        try:
            window.restore()
        except Exception:
            pass
        if sys.platform == "darwin":
            try:
                from AppKit import NSApplication  # type: ignore
                from webview.platforms import cocoa  # type: ignore

                uid = getattr(window, "uid", None)
                instances = list(cocoa.BrowserView.instances.values())
                targets = []
                if uid is not None and uid in cocoa.BrowserView.instances:
                    targets = [cocoa.BrowserView.instances[uid]]
                elif instances:
                    targets = instances
                shown = 0
                for i in targets:
                    nsw = getattr(i, "window", None)
                    if nsw is None:
                        continue
                    try:
                        nsw.deminiaturize_(nsw)
                    except Exception:
                        pass
                    nsw.makeKeyAndOrderFront_(nsw)
                    try:
                        nsw.orderFrontRegardless()
                    except Exception:
                        pass
                    shown += 1
                NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
                state.desk_log(f"window shown count={shown} instances={len(instances)}")
            except Exception as e:
                state.desk_log(f"native show failed: {e}")

    if sys.platform != "darwin":
        _do()
        return
    try:
        from AppKit import NSThread  # type: ignore
        from Foundation import NSOperationQueue  # type: ignore

        if NSThread.isMainThread():
            _do()
        else:
            NSOperationQueue.mainQueue().addOperationWithBlock_(_do)
    except Exception as e:
        state.desk_log(f"show schedule failed: {e}")
        try:
            _do()
        except Exception as e2:
            state.desk_log(f"show fallback failed: {e2}")


def _watch_show_requests(window, stop: threading.Event) -> None:
    clear_show()
    while not stop.is_set():
        try:
            if wait_show(0.5):
                state.desk_log("show request received")
                _show_window(window)
        except Exception as e:
            state.desk_log(f"show watcher error: {e}")


def _patch_cocoa_tray_lifecycle() -> None:
    from brain.desktop_cocoa import patch_tray_lifecycle

    patch_tray_lifecycle(show_window=_show_window)


def _schedule_tray_on_main(window) -> None:
    from brain.desktop_cocoa import schedule_tray_on_main

    schedule_tray_on_main(window, show_window=_show_window)


def _menu_bar_image():
    """Test/compat shim — real helper lives in desktop_cocoa."""
    from brain.desktop_cocoa import menu_bar_image

    return menu_bar_image()


def run_desktop(root: Path | None = None, port: int | None = None) -> None:
    try:
        import webview
    except ImportError as e:
        raise BrainError(
            "pywebview not installed. Reinstall BrainTools.pkg or: pip install pywebview"
        ) from e

    cfg = load_user_config()
    port = port or int(cfg.get("ui_port", 8765))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        busy = probe.connect_ex(("127.0.0.1", port)) == 0
    if busy:
        if _request_existing_show(port):
            print(f"Brain already running on :{port} — requested Show (menu bar / Dock)")
            state.desk_log(f"handoff to existing instance :{port}")
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        state.desk_log(f"port busy (non-brain); using free port={port}")

    if root is None:
        try:
            root = resolve_root()
        except BrainError:
            root = None

    _patch_cocoa_tray_lifecycle()

    t = threading.Thread(
        target=run_ui,
        kwargs={"root": root, "port": port},
        daemon=True,
        name="brain-ui-server",
    )
    t.start()
    _wait_ready(port)
    state.desk_log(f"desktop start port={port} root={root}")

    window = webview.create_window(
        title="Brain",
        url=f"http://127.0.0.1:{port}/",
        width=1280,
        height=840,
        min_size=(900, 600),
        background_color="#061018",
        text_select=True,
    )
    state.main_window = window

    def on_closing() -> bool:
        state.desk_log("closing event → stay alive (tray)")
        return False

    try:
        window.events.closing += on_closing
    except Exception as e:
        state.desk_log(f"closing hook failed: {e}")

    stop = threading.Event()

    def on_ready() -> None:
        _schedule_tray_on_main(window)
        threading.Thread(
            target=_watch_show_requests,
            args=(window, stop),
            daemon=True,
            name="brain-show-watch",
        ).start()

    try:
        webview.start(func=on_ready, private_mode=True)
    except Exception:
        state.desk_log("webview.start crashed:\n" + traceback.format_exc())
        raise
    finally:
        stop.set()
        state.desk_log("webview.start returned (process exiting)")
