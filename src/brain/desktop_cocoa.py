"""macOS Cocoa: close→tray, Dock reopen, menu-bar status item.

Imported only from `desktop.py` on darwin. Keeps AppKit/pywebview patches
out of the main orchestration module for reviewability.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from brain import desktop_state as state


def patch_tray_lifecycle(*, show_window) -> None:
    """Close button → hide; Cmd+Q / Dock Quit → quit; Dock click → show."""
    if sys.platform != "darwin":
        return
    try:
        import Foundation  # type: ignore
        from webview.platforms import cocoa  # type: ignore
    except Exception as e:
        state.desk_log(f"cocoa patch skipped (import): {e}")
        return

    def windowShouldClose_(self, window):  # noqa: N802, ANN001
        if state.allow_quit:
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
                state.desk_log("windowShouldClose → orderOut (stay in tray)")
        except Exception as e:
            state.desk_log(f"windowShouldClose hide failed: {e}")
        return Foundation.NO

    def applicationShouldTerminateAfterLastWindowClosed_(self, _app) -> bool:  # noqa: N802
        return False

    def applicationShouldTerminate_(self, app):  # noqa: N802, ANN001
        state.allow_quit = True
        state.desk_log("terminate allowed (Cmd+Q / Dock Quit)")
        return Foundation.YES

    def applicationShouldHandleReopen_hasVisibleWindows_(  # noqa: N802
        self, app, has_visible_windows
    ):
        state.desk_log(f"dock reopen hasVisible={bool(has_visible_windows)}")
        if state.main_window is not None:
            show_window(state.main_window)
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
                    applicationShouldTerminateAfterLastWindowClosed_.__get__(
                        shared, type(shared)
                    )
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
        state.desk_log("cocoa tray lifecycle patched")
    except Exception as e:
        state.desk_log(f"cocoa patch failed: {e}")


def menu_bar_image():
    """AppIcon (colored) preferred; SF Symbol fallback."""
    try:
        from AppKit import (  # type: ignore
            NSCompositingOperationSourceOver,
            NSImage,
        )
        from Foundation import NSMakeRect, NSZeroRect  # type: ignore
    except Exception as e:
        state.desk_log(f"tray image import failed: {e}")
        return None, None

    candidates: list[Path] = [
        Path("/Applications/Brain.app/Contents/Resources/AppIcon.icns"),
        Path("/usr/local/lib/brain-tools/Brain.app/Contents/Resources/AppIcon.icns"),
        Path("/usr/local/lib/brain-tools/packaging/macos/brain-icon-1024.png"),
    ]
    try:
        here = Path(__file__).resolve()
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
        try:
            out.setTemplate_(False)
        except Exception:
            pass
        return out, src_name
    except Exception as e:
        state.desk_log(f"tray image scale failed: {e}")
        return src, src_name


def _tray_delegate_class(*, show_window):
    if state.TrayDelegateCls is not None:
        return state.TrayDelegateCls
    from AppKit import NSApplication  # type: ignore
    from Foundation import NSObject  # type: ignore

    class TrayDelegate(NSObject):  # type: ignore[misc, valid-type]
        def showWindow_(self, _sender) -> None:  # noqa: N802
            show_window()

        def quitApp_(self, _sender) -> None:  # noqa: N802
            state.allow_quit = True
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

    state.TrayDelegateCls = TrayDelegate
    return TrayDelegate


def install_macos_tray(window, *, show_window) -> None:
    """Menu bar item with Show / Quit. Must run on AppKit main thread."""
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
        state.desk_log(f"tray AppKit import failed: {e}")
        return

    try:
        app = NSApplication.sharedApplication()
        try:
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        except Exception:
            pass

        bar = NSStatusBar.systemStatusBar()
        if state.tray_status is not None:
            try:
                bar.removeStatusItem_(state.tray_status)
            except Exception:
                pass
            state.tray_status = None

        TrayDelegate = _tray_delegate_class(show_window=show_window)
        delegate = TrayDelegate.alloc().init()
        img, img_name = menu_bar_image()
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

        state.tray_status = status
        state.tray_refs = [delegate, status, bar]
        window._brain_tray = status  # type: ignore[attr-defined]
        window._brain_tray_delegate = delegate  # type: ignore[attr-defined]

        bundle_id = bundle_path = None
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
                button.setTitle_("")
                try:
                    button.setImagePosition_(NSImageOnly)
                except Exception:
                    pass
                image_set = True
                state.tray_refs.append(img)
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
                state.desk_log(f"tray legacy set failed: {e}")

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
        state.tray_refs.extend([menu, show, quit_item])

        visible = None
        try:
            visible = bool(status.isVisible())
        except Exception:
            pass
        length_v = None
        try:
            length_v = float(status.length())
        except Exception:
            pass
        state.desk_log(
            f"tray installed image={img_name!s} image_set={image_set} "
            f"title_set={title_set} visible={visible} button={button is not None} "
            f"frame={frame_w}x{frame_h} length={length_v} "
            f"bundle_id={bundle_id!s} bundle={bundle_path!s}"
        )
    except Exception as e:
        state.desk_log(f"tray install failed: {e}")


def schedule_tray_on_main(window, *, show_window) -> None:
    if sys.platform != "darwin":
        return

    def _setup() -> None:
        install_macos_tray(window, show_window=show_window)

    scheduled = False
    try:
        from PyObjCTools import AppHelper  # type: ignore

        AppHelper.callAfter(_setup)
        scheduled = True
    except Exception as e:
        state.desk_log(f"tray AppHelper schedule failed: {e}")

    if not scheduled:
        try:
            from Foundation import NSOperationQueue  # type: ignore

            NSOperationQueue.mainQueue().addOperationWithBlock_(_setup)
            scheduled = True
        except Exception as e:
            state.desk_log(f"tray NSOperationQueue schedule failed: {e}")

    if not scheduled:
        try:
            _setup()
        except Exception as e:
            state.desk_log(f"tray schedule failed: {e}")
            return

    def _retry_later() -> None:
        time.sleep(1.5)
        state.desk_log("tray reinstall pass")
        try:
            from PyObjCTools import AppHelper  # type: ignore

            AppHelper.callAfter(
                lambda: install_macos_tray(window, show_window=show_window)
            )
            return
        except Exception:
            pass
        try:
            from Foundation import NSOperationQueue  # type: ignore

            NSOperationQueue.mainQueue().addOperationWithBlock_(
                lambda: install_macos_tray(window, show_window=show_window)
            )
        except Exception as e:
            state.desk_log(f"tray retry failed: {e}")

    threading.Thread(
        target=_retry_later, daemon=True, name="brain-tray-retry"
    ).start()
