"""Search index build and query."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from brain.cards import list_card_meta
from brain.paths import atomic_write_text


def index_path(root: Path) -> Path:
    return root / "index" / "search.json"


def rebuild_index(root: Path) -> list[dict[str, Any]]:
    items = list_card_meta(root)
    payload = {"version": 1, "cards": items}
    path = index_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        mode=0o644,
    )
    _write_map_md(root, items)
    # Lean agent catalog (token-cheap)
    from brain.recipes import write_catalog

    write_catalog(root, items)
    return items


def load_index(root: Path) -> list[dict[str, Any]]:
    path = index_path(root)
    if not path.is_file():
        return rebuild_index(root)
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("cards") or [])


def _tokenize(q: str) -> list[str]:
    return [t for t in re.split(r"\s+", q.strip().lower()) if t]


def search(root: Path, query: str, *, limit: int = 3) -> list[dict[str, Any]]:
    tokens = _tokenize(query)
    if not tokens:
        return []
    cards = load_index(root)
    scored: list[tuple[int, dict[str, Any]]] = []
    for c in cards:
        hay_title = (c.get("title") or "").lower()
        hay_id = (c.get("id") or "").lower()
        hay_tags = " ".join(c.get("tags") or []).lower()
        hay_tldr = (c.get("tldr") or "").lower()
        score = 0
        for t in tokens:
            if t == hay_id or t == hay_title:
                score += 100
            elif t in hay_id or t in hay_title:
                score += 50
            if t in hay_tags:
                score += 30
            if t in hay_tldr:
                score += 10
        if score:
            scored.append((score, c))
    scored.sort(key=lambda x: (-x[0], x[1].get("id") or ""))
    return [c for _, c in scored[:limit]]


def _write_map_md(root: Path, items: list[dict[str, Any]]) -> None:
    lines = ["# Knowledge map", "", "| id | title | tags |", "|----|-------|------|"]
    for c in items:
        tags = ", ".join(c.get("tags") or [])
        sec = " 🔒" if c.get("secure") else ""
        lines.append(f"| `{c.get('id')}` | {c.get('title')}{sec} | {tags} |")
    lines.append("")
    (root / "index" / "map.md").write_text("\n".join(lines), encoding="utf-8")
