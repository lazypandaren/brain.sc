"""Tests for Brain 0.4.2: desktop lifecycle helpers + hot-patch Python path."""

from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_module_imports():
    import brain.desktop as desktop

    assert callable(desktop.run_desktop)
    assert callable(desktop._show_window)
    assert callable(desktop._patch_cocoa_tray_lifecycle)


def test_hot_patch_scripts_resolve_purelib_not_hardcoded_312():
    """Install may use Python 3.10–3.13; scripts must not assume python3.12 only."""
    for rel in (
        "scripts/macos/hot-patch-0.4.1.sh",
        "scripts/macos/hot-patch-desktop.sh",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "sysconfig.get_path" in text, f"{rel} should resolve purelib via sysconfig"
        assert 'python3.12/site-packages' not in text, f"{rel} still hardcodes python3.12"


def test_brain_launcher_resolves_site_packages_dynamically():
    text = (ROOT / "packaging/macos/Brain-launcher.sh").read_text(encoding="utf-8")
    assert "sysconfig.get_path" in text
    assert "BrainPython" in text
    assert 'python3.12/site-packages' not in text


@pytest.mark.skipif(
    __import__("sys").platform != "darwin",
    reason="Cocoa tray helpers are macOS-only",
)
def test_menu_bar_image_helper_does_not_crash():
    from brain.desktop import _menu_bar_image

    _img, name = _menu_bar_image()
    # Image may be None in headless CI without AppKit assets; call must not raise.
    assert name is None or isinstance(name, str)
