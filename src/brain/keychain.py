"""macOS Keychain helpers for session wrap key (optional; file fallback)."""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Optional

SERVICE = "BrainTools"
ACCOUNT = "session-wrap-key"


def keychain_available() -> bool:
    return sys.platform == "darwin"


def get_wrap_key() -> Optional[bytes]:
    """Return 32-byte wrap key from Keychain, or None if missing/unavailable."""
    if not keychain_available():
        return None
    try:
        proc = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                SERVICE,
                "-a",
                ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    raw = (proc.stdout or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{64}", raw):
        return bytes.fromhex(raw)
    # legacy: raw base64-ish / binary as hex dump — reject unknown
    return None


def set_wrap_key(key: bytes) -> bool:
    if not keychain_available() or len(key) != 32:
        return False
    hex_key = key.hex()
    # delete existing (ignore failure)
    subprocess.run(
        [
            "/usr/bin/security",
            "delete-generic-password",
            "-s",
            SERVICE,
            "-a",
            ACCOUNT,
        ],
        capture_output=True,
        timeout=5,
        check=False,
    )
    proc = subprocess.run(
        [
            "/usr/bin/security",
            "add-generic-password",
            "-s",
            SERVICE,
            "-a",
            ACCOUNT,
            "-w",
            hex_key,
            "-U",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    return proc.returncode == 0


def backend_name() -> str:
    if get_wrap_key() is not None:
        return "keychain"
    return "file"
