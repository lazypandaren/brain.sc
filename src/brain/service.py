"""Detect whether Brain UI is listening on localhost."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any

from brain.config import load_user_config


def ui_port(cfg: dict[str, Any] | None = None) -> int:
    cfg = cfg or load_user_config()
    try:
        return int(cfg.get("ui_port", 8765))
    except (TypeError, ValueError):
        return 8765


def ui_is_running(port: int | None = None) -> bool:
    port = port if port is not None else ui_port()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.35):
            return True
    except OSError:
        return False


def probe_ui(port: int | None = None) -> dict[str, Any]:
    """Classify localhost UI port: down / brain_ok / port_busy_non_brain."""
    port = port if port is not None else ui_port()
    if not ui_is_running(port):
        return {"state": "down", "port": port}
    url = f"http://127.0.0.1:{port}/api/status"
    try:
        with urllib.request.urlopen(url, timeout=0.6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict) and (data.get("ui_running") or data.get("version")):
            return {
                "state": "brain_ok",
                "port": port,
                "version": data.get("version"),
                "root": data.get("root"),
            }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        pass
    return {"state": "port_busy_non_brain", "port": port}
