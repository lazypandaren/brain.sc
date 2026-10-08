"""Project hubs: tag `hub` entry points + alias matching for AI write-back.

Hubs are intentional (not degree-ranked). Each hub TL;DR should list aliases
so `brain hub suggest` / agents can file new cards without a long project essay.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from brain.cards import Card, add_link, list_card_meta, read_card, write_card
from brain.errors import VaultError
from brain.importer import slugify
from brain.paths import validate_slug

_ALIAS_LINE = re.compile(
    r"(?im)^\s*(?:aliases?|аліаси|алиасы)\s*:\s*(.+)$"
)
_SPLIT = re.compile(r"[,;/|]+|\s+/\s+")


@dataclass(frozen=True)
class HubInfo:
    id: str
    title: str
    tldr: str
    aliases: list[str]
    projects: list[str]


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9._-]{1,}", text.lower()) if t]


def parse_aliases(tldr: str, *, title: str = "", slug: str = "") -> list[str]:
    """Extract searchable aliases from hub TL;DR (+ title/slug)."""
    found: list[str] = []
    m = _ALIAS_LINE.search(tldr or "")
    raw = m.group(1) if m else (tldr or "")
    for part in _SPLIT.split(raw):
        part = part.strip().strip("[]()`\"'")
        if len(part) < 2:
            continue
        # Drop markdown link targets that look like prose sentences
        if " " in part and len(part) > 40:
            continue
        found.append(part)
    if title:
        found.append(title)
    if slug:
        found.append(slug.replace("-", " "))
        found.append(slug)
    # Dedupe case-insensitively, keep order
    out: list[str] = []
    seen: set[str] = set()
    for a in found:
        key = a.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out[:24]


def list_hubs(root: Path) -> list[HubInfo]:
    hubs: list[HubInfo] = []
    for meta in list_card_meta(root):
        tags = [str(t).lower() for t in (meta.get("tags") or [])]
        if "hub" not in tags:
            continue
        slug = str(meta["id"])
        tldr = str(meta.get("tldr") or "")
        title = str(meta.get("title") or slug)
        hubs.append(
            HubInfo(
                id=slug,
                title=title,
                tldr=tldr,
                aliases=parse_aliases(tldr, title=title, slug=slug),
                projects=[str(p) for p in (meta.get("projects") or [])],
            )
        )
    hubs.sort(key=lambda h: h.id)
    return hubs


def _score_hub(hub: HubInfo, query: str) -> float:
    q = (query or "").strip().lower()
    if not q:
        return 0.0
    score = 0.0
    if hub.id.lower() in q or q in hub.id.lower():
        score += 5.0
    if hub.title.lower() in q or q in hub.title.lower():
        score += 3.0
    q_tokens = set(_tokens(q))
    for alias in hub.aliases:
        al = alias.lower()
        if al in q or q in al:
            score += 4.0 + min(len(al), 20) * 0.05
            continue
        a_tokens = set(_tokens(al))
        overlap = q_tokens & a_tokens
        if overlap:
            score += 1.5 * len(overlap)
    return score


def suggest_hubs(root: Path, text: str, *, limit: int = 3) -> list[dict[str, Any]]:
    """Rank hubs for write-back given free text (ticket, repo, product name)."""
    ranked: list[tuple[float, HubInfo]] = []
    for hub in list_hubs(root):
        s = _score_hub(hub, text)
        if s > 0:
            ranked.append((s, hub))
    ranked.sort(key=lambda x: (-x[0], x[1].id))
    out: list[dict[str, Any]] = []
    for score, hub in ranked[: max(1, limit)]:
        out.append(
            {
                "id": hub.id,
                "title": hub.title,
                "score": round(score, 2),
                "aliases": hub.aliases[:12],
                "tldr": hub.tldr[:240],
            }
        )
    return out


def create_hub(
    root: Path,
    slug: str,
    *,
    title: str | None = None,
    aliases: list[str] | None = None,
    project: str | None = None,
    blurb: str | None = None,
) -> Card:
    """Create (or refresh) a project hub card with tag `hub` + alias TL;DR."""
    slug = validate_slug(slugify(slug) if slug else "")
    if not slug:
        raise VaultError("hub slug required")
    title = (title or slug.replace("-", " ")).strip()
    aliases = [a.strip() for a in (aliases or []) if a.strip()]
    if slug not in aliases:
        aliases = [slug, *aliases]
    if title not in aliases:
        aliases.append(title)
    # Dedup
    aliases = parse_aliases(
        "Aliases: " + ", ".join(aliases), title=title, slug=slug
    )
    alias_line = ", ".join(aliases[:16])
    blurb = (blurb or "Project hub — AI write-back: match aliases, then [[hub]].").strip()
    projects = [project] if project else []
    body = (
        f"# TL;DR\n"
        f"Aliases: {alias_line}\n"
        f"{blurb}\n\n"
        f"## Details\n"
        f"Tag `hub` = intentional entry point (not graph degree).\n"
        f"Keep 5–10 aliases fresh so `brain hub suggest` / agents file cards here.\n"
        f"Map: [[vault-map]] · protocol: [[how-to-use-brain]]\n"
    )
    # Preserve existing links if overwriting
    links: list[str] = ["vault-map", "how-to-use-brain"]
    try:
        existing = read_card(root, slug)
        for x in existing.links:
            if x not in links:
                links.append(x)
        tags = list(dict.fromkeys([*existing.tags, "hub", "project"]))
        if existing.projects and not projects:
            projects = list(existing.projects)
    except Exception:
        tags = ["hub", "project"]
    card = Card(
        id=slug,
        title=title,
        tags=tags,
        projects=projects,
        links=links,
        body=body,
        updated=date.today().isoformat(),
    )
    write_card(root, card)
    # Best-effort link from vault-map
    try:
        add_link(root, "vault-map", slug)
    except Exception:
        pass
    return card


def ensure_hub_link(root: Path, card_slug: str, hub_slug: str) -> None:
    """Link a card to its hub both ways (wiki graph)."""
    add_link(root, validate_slug(card_slug), validate_slug(hub_slug))
