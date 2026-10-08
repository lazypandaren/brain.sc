"""Native desktop window (pywebview) + macOS menu-bar tray (close → tray).

Stability:
- Single instance: if Brain already listens on the UI port, ask it to Show and exit.
- Closing the window hides to tray/Dock — does not quit the process.
- Cocoa: patch pywebview AppDelegate / WindowDelegate so hide never tears down the run loop.
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

from brain.config import load_user_config, resolve_root
from brain.desktop_ipc import clear_show, request_show, wait_show
from brain.errors import BrainError
from brain.ui_server import run_ui

_allow_quit = False
_keepalive_ref = None  # strong refs so PyObjC objects are not GC'd
_tray_refs: list = []


def _log_path() -> Path:
    return Path.home() / "Library" / "Logs" / "BrainTools" / "desktop.log"


def _desk_log(msg: str) -> None:
    try:
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")
    except Exception:
        pass


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
            _desk_log(f"requested show on existing instance port={port} http={ok}")
            return ok
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        _desk_log(f"show HTTP failed (file flag still set): {e}")
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


def _patch_cocoa_tray_lifecycle() -> None:
    """Keep NSApp alive when the pywebview window is hidden (close → tray).

    pywebview's Cocoa backend calls app.stop_() in windowWillClose_ when the last
    BrowserView is gone. Returning False from events.closing is not enough on its
    own if the AppKit close path still runs — we hard-block windowShouldClose_
    unless Quit was chosen, and cancel application terminate (Cmd+Q → hide).
    """
    if sys.platform != "darwin":
        return
    try:
        import Foundation  # type: ignore
        from webview.platforms import cocoa  # type: ignore
    except Exception as e:
        _desk_log(f"cocoa patch skipped (import): {e}")
        return

    def windowShouldClose_(self, window):  # noqa: N802, ANN001
        global _allow_quit
        if _allow_quit:
            return Foundation.YES
        try:
            i = cocoa.BrowserView.get_instance("window", window)
            if i is not None:
                # Hide on the AppKit side immediately (same as BrowserView.hide)
                try:
                    i.window.orderOut_(i.window)
                except Exception:
                    try:
                        i.hide()
                    except Exception:
                        pass
                _desk_log("windowShouldClose → orderOut (stay in tray)")
        except Exception as e:
            _desk_log(f"windowShouldClose hide failed: {e}")
        return Foundation.NO

    def applicationShouldTerminateAfterLastWindowClosed_(self, _app) -> bool:  # noqa: N802
        return False

    def applicationShouldTerminate_(self, app):  # noqa: N802, ANN001
        global _allow_quit
        if _allow_quit:
            return Foundation.YES
        # Cmd+Q / Dock Quit → tray, same as red traffic light
        try:
            for i in list(cocoa.BrowserView.instances.values()):
                try:
                    i.window.orderOut_(i.window)
                except Exception:
                    try:
                        i.hide()
                    except Exception:
                        pass
            _desk_log("terminate cancelled → hide (Cmd+Q → tray)")
        except Exception as e:
            _desk_log(f"terminate-hide failed: {e}")
        return Foundation.NO

    try:
        cocoa.BrowserView.WindowDelegate.windowShouldClose_ = windowShouldClose_
        # Subclass so newly allocated AppDelegate gets both methods
        Base = cocoa.BrowserView.AppDelegate

        class BrainAppDelegate(Base):  # type: ignore[misc, valid-type]
            pass

        BrainAppDelegate.applicationShouldTerminateAfterLastWindowClosed_ = (  # type: ignore[method-assign]
            applicationShouldTerminateAfterLastWindowClosed_
        )
        BrainAppDelegate.applicationShouldTerminate_ = applicationShouldTerminate_  # type: ignore[method-assign]
        cocoa.BrowserView.AppDelegate = BrainAppDelegate
        # If pywebview already installed a shared delegate, swap methods on it too
        shared = getattr(cocoa.BrowserView, "_shared_app_delegate", None)
        if shared is not None:
            try:
                shared.applicationShouldTerminateAfterLastWindowClosed_ = (  # type: ignore[method-assign]
                    applicationShouldTerminateAfterLastWindowClosed_.__get__(shared, type(shared))
                )
            except Exception:
                pass
        _desk_log("cocoa tray lifecycle patched")
    except Exception as e:
        _desk_log(f"cocoa patch failed: {e}")


def _install_macos_tray(window) -> None:
    """Menu bar item 🧠 with Show / Quit. Must run on AppKit main thread."""
    global _tray_refs
    try:
        from AppKit import (  # type: ignore
            NSApplication,
            NSApplicationActivationPolicyRegular,
            NSMenu,
            NSMenuItem,
            NSStatusBar,
            NSVariableStatusItemLength,
        )
        from Foundation import NSObject  # type: ignore
    except Exception as e:
        _desk_log(f"tray AppKit import failed: {e}")
        return

    class TrayDelegate(NSObject):  # type: ignore[misc, valid-type]
        def showWindow_(self, _sender) -> None:  # noqa: N802
            _show_window(window)

        def quitApp_(self, _sender) -> None:  # noqa: N802
            global _allow_quit
            _allow_quit = True
            try:
                import webview

                for w in list(webview.windows):
                    try:
                        w.destroy()
                    except Exception:
                        pass
            except Exception:
                pass
            NSApplication.sharedApplication().terminate_(None)

    try:
        app = NSApplication.sharedApplication()
        try:
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        except Exception:
            pass

        delegate = TrayDelegate.alloc().init()
        status = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength
        )
        _tray_refs = [delegate, status]
        window._brain_tray = status  # type: ignore[attr-defined]
        window._brain_tray_delegate = delegate  # type: ignore[attr-defined]

        button = status.button()
        if button is not None:
            button.setTitle_("🧠")
            button.setToolTip_("Brain — Показати / Вийти")

        menu = NSMenu.alloc().init()
        show = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Показати Brain", "showWindow:", ""
        )
        show.setTarget_(delegate)
        menu.addItem_(show)
        menu.addItem_(NSMenuItem.separatorItem())
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Вийти", "quitApp:", "q"
        )
        quit_item.setTarget_(delegate)
        menu.addItem_(quit_item)
        status.setMenu_(menu)
        _desk_log("tray installed")
    except Exception as e:
        _desk_log(f"tray install failed: {e}")
        return


def _show_window(window) -> None:
    """Bring Brain window forward — must run on AppKit main thread (macOS)."""

    def _do() -> None:
        # Must return None for NSBlock
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

                i = cocoa.BrowserView.instances.get(getattr(window, "uid", None))
                if i is not None and getattr(i, "window", None) is not None:
                    i.window.deminiaturize_(i.window)
                    i.window.makeKeyAndOrderFront_(i.window)
                    i.window.orderFrontRegardless()
                NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
                _desk_log("window shown")
            except Exception as e:
                _desk_log(f"native show failed: {e}")

    if sys.platform != "darwin":
        _do()
        return
    try:
        from Foundation import NSOperationQueue  # type: ignore
        from AppKit import NSThread  # type: ignore

        if NSThread.isMainThread():
            _do()
        else:
            NSOperationQueue.mainQueue().addOperationWithBlock_(_do)
    except Exception as e:
        _desk_log(f"show schedule failed: {e}")
        try:
            _do()
        except Exception as e2:
            _desk_log(f"show fallback failed: {e2}")


def _watch_show_requests(window, stop: threading.Event) -> None:
    clear_show()
    while not stop.is_set():
        try:
            if wait_show(0.5):
                _desk_log("show request received")
                _show_window(window)
        except Exception as e:
            _desk_log(f"show watcher error: {e}")


def _schedule_tray_on_main(window) -> None:
    if sys.platform != "darwin":
        return

    def _setup() -> None:
        # Must return None — NSBlockOperation rejects non-void Python returns
        _install_macos_tray(window)

    try:
        from Foundation import NSOperationQueue  # type: ignore

        NSOperationQueue.mainQueue().addOperationWithBlock_(_setup)
    except Exception:
        try:
            _setup()
        except Exception as e:
            _desk_log(f"tray schedule failed: {e}")


def run_desktop(root: Path | None = None, port: int | None = None) -> None:
    try:
        import webview
    except ImportError as e:
        raise BrainError(
            "pywebview not installed. Reinstall BrainTools.pkg or: pip install pywebview"
        ) from e

    cfg = load_user_config()
    port = port or int(cfg.get("ui_port", 8765))

    # Single instance: port already served by Brain → ask it to show, then exit.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        busy = probe.connect_ex(("127.0.0.1", port)) == 0
    if busy:
        if _request_existing_show(port):
            print(f"Brain already running on :{port} — requested Show (menu bar 🧠 / Dock)")
            _desk_log(f"handoff to existing instance :{port}")
            return
        # Not our API (or stuck) — pick a free port for a new instance
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        _desk_log(f"port busy (non-brain); using free port={port}")

    if root is None:
        try:
            root = resolve_root()
        except BrainError:
            root = None

    # Before any NSWindow / AppDelegate is created
    _patch_cocoa_tray_lifecycle()

    t = threading.Thread(
        target=run_ui,
        kwargs={"root": root, "port": port},
        daemon=True,
        name="brain-ui-server",
    )
    t.start()
    _wait_ready(port)
    _desk_log(f"desktop start port={port} root={root}")

    window = webview.create_window(
        title="Brain",
        url=f"http://127.0.0.1:{port}/",
        width=1280,
        height=840,
        min_size=(900, 600),
        background_color="#061018",
        text_select=True,
    )

    def on_closing() -> bool:
        # Belt-and-suspenders with windowShouldClose_ patch
        try:
            window.hide()
            _desk_log("window hidden (close → tray)")
        except Exception as e:
            _desk_log(f"hide failed: {e}")
        return False

    try:
        window.events.closing += on_closing
    except Exception as e:
        _desk_log(f"closing hook failed: {e}")

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
        _desk_log("webview.start crashed:\n" + traceback.format_exc())
        raise
    finally:
        stop.set()
        _desk_log("webview.start returned (process exiting)")
