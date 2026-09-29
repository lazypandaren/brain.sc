"""Save in-app questionnaire answers as a portable feedback artifact."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from brain import __version__
from brain.paths import atomic_write_text

# Whitelisted structured fields: (key, kind)
FIELDS = [
    ("tester", "str"),
    ("platform", "str"),
    ("install_ok", "bool"),
    ("first_run_clear", "bool"),
    ("search_ok", "bool"),
    ("import_ok", "bool"),
    ("dashboard_useful", "bool"),
    ("trust_encryption", "bool"),
    ("would_use_daily", "bool"),
    ("score", "int"),
    ("top_fix", "str"),
]


def _coerce(value: Any, kind: str) -> Any:
    if value is None or value == "":
        return None
    if kind == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "yes", "так", "да", "1")
    if kind == "int":
        try:
            return max(0, min(10, int(value)))
        except (TypeError, ValueError):
            return None
    return str(value).strip()[:300]


def save_feedback(root: Path, answers: dict[str, Any], comments: str) -> Path:
    now = datetime.now()
    lines = [
        "---",
        "type: feedback",
        "product: brain-tools",
        f"version: {__version__}",
        f"date: {now.strftime('%Y-%m-%d %H:%M')}",
    ]
    for key, kind in FIELDS:
        val = _coerce(answers.get(key), kind)
        if val is None:
            lines.append(f"{key}: null")
        elif isinstance(val, bool):
            lines.append(f"{key}: {'true' if val else 'false'}")
        elif isinstance(val, int):
            lines.append(f"{key}: {val}")
        else:
            escaped = str(val).replace('"', "'")
            lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    lines.append("")
    lines.append(f"# Feedback — Brain {__version__}")
    lines.append("")
    lines.append("## Коментарі")
    lines.append("")
    lines.append(comments.strip()[:8000] or "(порожньо)")
    lines.append("")

    out_dir = root / "feedback"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"feedback-{now.strftime('%Y%m%d-%H%M%S')}.md"
    atomic_write_text(path, "\n".join(lines))
    return path


def reveal_in_finder(path: Path) -> None:
    """Best-effort: show the file in Finder so it's easy to send."""
    if sys.platform == "darwin":
        try:
            subprocess.Popen(["/usr/bin/open", "-R", str(path)])
        except OSError:
            pass
