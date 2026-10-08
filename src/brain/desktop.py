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
_tray_status = None  # NSStatusItem — keep for remove/reinstall
_main_window = None  # pywebview window — Dock reopen / tray Show
_TrayDelegateCls = None  # NSObject subclass — create once (PyObjC)


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
    """Close button → hide to tray; Cmd+Q / Dock Quit → real quit.

    pywebview's Cocoa backend calls app.stop_() in windowWillClose_ when the last
    BrowserView is gone. We block windowShouldClose_ unless Quit was chosen so the
    red traffic light only hides. Cmd+Q must terminate — otherwise Force Quit is
    the only escape when the menu-bar icon is missing.
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
        # Cmd+Q / Dock Quit = real exit (not hide). Close button still trays.
        global _allow_quit
        _allow_quit = True
        _desk_log("terminate allowed (Cmd+Q / Dock Quit)")
        return Foundation.YES

    def applicationShouldHandleReopen_hasVisibleWindows_(  # noqa: N802
        self, app, has_visible_windows
    ):
        # Dock icon click after orderOut (close → tray): restore window.
        _desk_log(f"dock reopen hasVisible={bool(has_visible_windows)}")
        if _main_window is not None:
            _show_window(_main_window)
        return Foundation.YES

    try:
        cocoa.BrowserView.WindowDelegate.windowShouldClose_ = windowShouldClose_
        Base = cocoa.BrowserView.AppDelegate

        class BrainAppDelegate(Base):  # type: ignore[misc, valid-type]
            pass

        BrainAppDelegate.applicationShouldTerminateAfterLastWindowClosed_ = (  # type: ignore[method-assign]
            applicationShouldTerminateAfterLastWindowClosed_
        )
        BrainAppDelegate.applicationShouldTerminate_ = applicationShouldTerminate_  # type: ignore[method-assign]
        BrainAppDelegate.applicationShouldHandleReopen_hasVisibleWindows_ = (  # type: ignore[method-assign]
            applicationShouldHandleReopen_hasVisibleWindows_
        )
        cocoa.BrowserView.AppDelegate = BrainAppDelegate
        shared = getattr(cocoa.BrowserView, "_shared_app_delegate", None)
        if shared is not None:
            try:
                shared.applicationShouldTerminateAfterLastWindowClosed_ = (  # type: ignore[method-assign]
                    applicationShouldTerminateAfterLastWindowClosed_.__get__(shared, type(shared))
                )
                shared.applicationShouldTerminate_ = (  # type: ignore[method-assign]
                    applicationShouldTerminate_.__get__(shared, type(shared))
                )
                shared.applicationShouldHandleReopen_hasVisibleWindows_ = (  # type: ignore[method-assign]
                    applicationShouldHandleReopen_hasVisibleWindows_.__get__(
                        shared, type(shared)
                    )
                )
            except Exception:
                pass
        _desk_log("cocoa tray lifecycle patched")
    except Exception as e:
        _desk_log(f"cocoa patch failed: {e}")


def _menu_bar_image():
    """Menu-bar icon: AppIcon (colored) preferred; SF Symbol fallback.

    SF Symbol templates often render blank for non-bundled Python hosts on
    recent macOS — AppIcon.icns + title is the reliable pair.
    """
    try:
        from AppKit import (  # type: ignore
            NSCompositingOperationSourceOver,
            NSImage,
        )
        from Foundation import NSMakeRect, NSZeroRect  # type: ignore
    except Exception as e:
        _desk_log(f"tray image import failed: {e}")
        return None, None

    candidates: list[Path] = [
        Path("/Applications/Brain.app/Contents/Resources/AppIcon.icns"),
        Path("/usr/local/lib/brain-tools/Brain.app/Contents/Resources/AppIcon.icns"),
        Path("/usr/local/lib/brain-tools/packaging/macos/brain-icon-1024.png"),
    ]
    try:
        here = Path(__file__).resolve()
        # site-packages/brain/desktop.py → …/brain-tools or repo src/brain
        for up in (here.parents[2], here.parents[3]):
            candidates.append(up / "packaging" / "macos" / "brain-icon-1024.png")
            candidates.append(
                up / "Brain.app" / "Contents" / "Resources" / "AppIcon.icns"
            )
    except Exception:
        pass

    src = None
    src_name = None
    for p in candidates:
        try:
            if not p.is_file():
                continue
            loaded = NSImage.alloc().initWithContentsOfFile_(str(p))
            if loaded is not None:
                src, src_name = loaded, str(p)
                break
        except Exception:
            continue

    if src is None:
        try:
            src = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "brain", "Brain"
            )
            src_name = "sf:brain"
        except Exception:
            src = None
        if src is None:
            return None, None

    try:
        size = 18.0
        out = NSImage.alloc().initWithSize_((size, size))
        out.lockFocus()
        src.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, size, size),
            NSZeroRect,
            NSCompositingOperationSourceOver,
            1.0,
        )
        out.unlockFocus()
        # Colored (non-template) — template SF Symbols were invisible in practice
        try:
            out.setTemplate_(False)
        except Exception:
            pass
        return out, src_name
    except Exception as e:
        _desk_log(f"tray image scale failed: {e}")
        return src, src_name


def _tray_delegate_class():
    """Create TrayDelegate once — redefining NSObject subclasses breaks PyObjC targets."""
    global _TrayDelegateCls
    if _TrayDelegateCls is not None:
        return _TrayDelegateCls
    from AppKit import NSApplication  # type: ignore
    from Foundation import NSObject  # type: ignore

    class TrayDelegate(NSObject):  # type: ignore[misc, valid-type]
        def showWindow_(self, _sender) -> None:  # noqa: N802
            _show_window()

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

    _TrayDelegateCls = TrayDelegate
    return TrayDelegate


def _install_macos_tray(window) -> None:
    """Menu bar item with Show / Quit. Must run on AppKit main thread."""
    global _tray_refs, _tray_status
    try:
        from AppKit import (  # type: ignore
            NSApplication,
            NSApplicationActivationPolicyRegular,
            NSImageOnly,
            NSMenu,
            NSMenuItem,
            NSSquareStatusItemLength,
            NSStatusBar,
            NSVariableStatusItemLength,
        )
    except Exception as e:
        _desk_log(f"tray AppKit import failed: {e}")
        return

    try:
        app = NSApplication.sharedApplication()
        try:
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        except Exception:
            pass

        bar = NSStatusBar.systemStatusBar()
        # Drop previous item if we re-install (avoids ghost / lost refs)
        if _tray_status is not None:
            try:
                bar.removeStatusItem_(_tray_status)
            except Exception:
                pass
            _tray_status = None

        TrayDelegate = _tray_delegate_class()
        delegate = TrayDelegate.alloc().init()
        img, img_name = _menu_bar_image()
        # Prefer compact square icon (fits notch). Title-only if image missing.
        length = (
            NSSquareStatusItemLength if img is not None else NSVariableStatusItemLength
        )
        status = bar.statusItemWithLength_(length)
        try:
            status.retain()
            delegate.retain()
        except Exception:
            pass
        try:
            status.setVisible_(True)
        except Exception:
            pass
        # Do NOT set autosaveName — macOS can permanently hide the item after
        # Cmd-drag / Control Center toggle and keep that preference.

        # Keep strong refs forever — otherwise GC removes the menu-bar icon
        _tray_status = status
        _tray_refs = [delegate, status, bar]
        window._brain_tray = status  # type: ignore[attr-defined]
        window._brain_tray_delegate = delegate  # type: ignore[attr-defined]

        bundle_id = None
        bundle_path = None
        try:
            from Foundation import NSBundle  # type: ignore

            b = NSBundle.mainBundle()
            bundle_id = str(b.bundleIdentifier() or "")
            bundle_path = str(b.bundlePath() or "")
        except Exception:
            pass


        button = status.button()
        title_set = False
        image_set = False
        frame_w = frame_h = None
        if button is not None:
            button.setToolTip_("Brain — Show / Quit")
            if img is not None:
                button.setImage_(img)
                button.setTitle_("")  # icon-only keeps ~22pt — survives notch crowding
                try:
                    button.setImagePosition_(NSImageOnly)
                except Exception:
                    pass
                image_set = True
                _tray_refs.append(img)
            else:
                button.setTitle_("Brain")
                title_set = True
            try:
                button.setEnabled_(True)
                button.setHidden_(False)
            except Exception:
                pass
            try:
                fr = button.frame()
                frame_w = float(fr.size.width)
                frame_h = float(fr.size.height)
            except Exception:
                pass
        else:
            try:
                if img is not None:
                    status.setImage_(img)
                    image_set = True
                else:
                    status.setTitle_("Brain")
                    title_set = True
            except Exception as e:
                _desk_log(f"tray legacy set failed: {e}")

        menu = NSMenu.alloc().init()
        show = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Brain", "showWindow:", ""
        )
        show.setTarget_(delegate)
        menu.addItem_(show)
        menu.addItem_(NSMenuItem.separatorItem())
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit", "quitApp:", ""
        )
        quit_item.setTarget_(delegate)
        menu.addItem_(quit_item)
        status.setMenu_(menu)
        try:
            menu.retain()
        except Exception:
            pass
        _tray_refs.extend([menu, show, quit_item])

        visible = None
        try:
            visible = bool(status.isVisible())
        except Exception:
            pass
        length = None
        try:
            length = float(status.length())
        except Exception:
            pass
        _desk_log(
            f"tray installed image={img_name!s} image_set={image_set} "
            f"title_set={title_set} visible={visible} button={button is not None} "
            f"frame={frame_w}x{frame_h} length={length} "
            f"bundle_id={bundle_id!s} bundle={bundle_path!s}"
        )
    except Exception as e:
        _desk_log(f"tray install failed: {e}")
        return


def _show_window(window=None) -> None:
    """Bring Brain window forward — must run on AppKit main thread (macOS)."""
    window = window or _main_window
    if window is None:
        _desk_log("show skipped: no window ref")
        return

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
                _desk_log(f"window shown count={shown} instances={len(instances)}")
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
        # Must return None — NSBlockOperation / callAfter reject non-void returns
        _install_macos_tray(window)

    scheduled = False
    # Prefer PyObjCTools.AppHelper.callAfter — same runloop path as pywebview Cocoa
    try:
        from PyObjCTools import AppHelper  # type: ignore

        AppHelper.callAfter(_setup)
        scheduled = True
    except Exception as e:
        _desk_log(f"tray AppHelper schedule failed: {e}")

    if not scheduled:
        try:
            from Foundation import NSOperationQueue  # type: ignore

            NSOperationQueue.mainQueue().addOperationWithBlock_(_setup)
            scheduled = True
        except Exception as e:
            _desk_log(f"tray NSOperationQueue schedule failed: {e}")

    if not scheduled:
        try:
            _setup()
        except Exception as e:
            _desk_log(f"tray schedule failed: {e}")
            return

    def _retry_later() -> None:
        time.sleep(1.5)
        _desk_log("tray reinstall pass")
        try:
            from PyObjCTools import AppHelper  # type: ignore

            AppHelper.callAfter(lambda: _install_macos_tray(window))
            return
        except Exception:
            pass
        try:
            from Foundation import NSOperationQueue  # type: ignore

            NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: _install_macos_tray(window)
            )
        except Exception as e:
            _desk_log(f"tray retry failed: {e}")

    threading.Thread(
        target=_retry_later, daemon=True, name="brain-tray-retry"
    ).start()


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

    global _main_window
    window = webview.create_window(
        title="Brain",
        url=f"http://127.0.0.1:{port}/",
        width=1280,
        height=840,
        min_size=(900, 600),
        background_color="#061018",
        text_select=True,
    )
    _main_window = window

    def on_closing() -> bool:
        # Cocoa windowShouldClose_ already orderOuts; keep False so process stays.
        # Do not call window.hide() here — races with Dock reopen / show.
        _desk_log("closing event → stay alive (tray)")
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
