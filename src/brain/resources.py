"""Resolve install / repo root for UI and agent snippets."""

from __future__ import annotations

import os
from pathlib import Path

# Prefer explicit override (set by installer wrapper)
ENV_ROOT = "BRAIN_TOOLS_HOME"


def tools_home() -> Path:
    env = os.environ.get(ENV_ROOT)
    if env:
        p = Path(env).expanduser().resolve()
        if p.is_dir():
            return p

    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent.parent,  # repo: src/brain/x.py -> repo
        Path("/usr/local/lib/brain-tools"),
        Path.home() / "Library" / "Application Support" / "BrainTools",
    ]
    for c in candidates:
        if (c / "ui" / "index.html").is_file() and (c / "agents" / "snippets").is_dir():
            return c
        if (c / "pyproject.toml").is_file() and (c / "ui").is_dir():
            return c
    # Fallback: development layout even if ui missing (tests)
    return here.parent.parent.parent


def ui_dir() -> Path:
    return tools_home() / "ui"


def snippets_dir() -> Path:
    return tools_home() / "agents" / "snippets"
