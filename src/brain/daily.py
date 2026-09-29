"""Daily notes (Obsidian-style day cards) + backlink helpers."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from brain.cards import Card, list_card_meta, read_card, write_card
from brain.errors import NotFoundError
from brain.index import load_index, rebuild_index
from brain.paths import validate_slug


def daily_slug(day: date | None = None) -> str:
    d = day or date.today()
    return f"daily-{d.isoformat()}"


def ensure_daily(root: Path, day: date | None = None) -> Card:
    """Create or return today's (or given) daily card."""
    d = day or date.today()
    slug = daily_slug(d)
    try:
        return read_card(root, slug)
    except NotFoundError:
        pass

    prev = d - timedelta(days=1)
    prev_slug = daily_slug(prev)
    links: list[str] = []
    # Link previous day if it exists
    try:
        read_card(root, prev_slug)
        links.append(prev_slug)
    except NotFoundError:
        pass

    body = (
        f"# TL;DR\n"
        f"Daily note for {d.isoformat()}. Capture scratch → promote durable facts to real cards.\n\n"
        f"## Details\n\n"
        f"- Focus:\n"
        f"- Done:\n"
        f"- Remember:\n\n"
    )
    if links:
        body += f"Previous: [[{links[0]}]]\n"

    card = Card(
        id=slug,
        title=f"Daily {d.isoformat()}",
        tags=["daily"],
        links=links,
        body=body,
    )
    write_card(root, card)
    rebuild_index(root)
    return read_card(root, slug)


def backlinks(root: Path, slug: str) -> list[dict[str, Any]]:
    """Cards that link to slug (frontmatter and/or wiki-links, from index)."""
    slug = validate_slug(slug)
    items = load_index(root) or list_card_meta(root)
    out: list[dict[str, Any]] = []
    for c in items:
        cid = c.get("id")
        if not cid or cid == slug:
            continue
        if slug in (c.get("links") or []):
            out.append(
                {
                    "id": cid,
                    "title": c.get("title") or cid,
                    "tldr": (c.get("tldr") or "")[:200],
                }
            )
    out.sort(key=lambda x: str(x.get("id") or ""))
    return out


def inbound_map(root: Path) -> dict[str, list[str]]:
    """slug → list of card ids that link to it."""
    items = load_index(root) or list_card_meta(root)
    inbound: dict[str, list[str]] = {}
    for c in items:
        src = c.get("id")
        if not src:
            continue
        for dst in c.get("links") or []:
            inbound.setdefault(dst, []).append(src)
    return inbound
