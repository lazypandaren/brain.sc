"""Card read/write, frontmatter, secure encrypt."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from brain.crypto import decrypt, encrypt
from brain.errors import LockedError, NotFoundError, VaultError
from brain.paths import atomic_write_bytes, atomic_write_text, safe_join, validate_slug
from brain.session import get_session_key, is_unlocked

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass
class Card:
    id: str
    title: str
    tags: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    secure: bool = False
    updated: str = ""
    body: str = ""
    path: Path | None = None

    @property
    def tldr(self) -> str:
        text = self.body
        # Prefer # TL;DR section
        m = re.search(
            r"^#\s*TL;DR\s*\n(.*?)(?=^#|\Z)", text, re.MULTILINE | re.DOTALL | re.IGNORECASE
        )
        if m:
            return m.group(1).strip().split("\n\n")[0].strip()[:500]
        # First non-empty paragraph
        for block in text.split("\n\n"):
            line = block.strip()
            if line and not line.startswith("#"):
                return line[:500]
        return self.title


def parse_card(text: str, *, path: Path | None = None, secure: bool = False) -> Card:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise VaultError("Card missing YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise VaultError("Invalid frontmatter")
    cid = validate_slug(str(meta.get("id") or (path.stem if path else "")))
    return Card(
        id=cid,
        title=str(meta.get("title") or cid),
        tags=[str(t) for t in (meta.get("tags") or [])],
        projects=[str(p) for p in (meta.get("projects") or [])],
        links=[validate_slug(str(x)) for x in (meta.get("links") or [])],
        secure=bool(meta.get("secure", secure)),
        updated=str(meta.get("updated") or ""),
        body=m.group(2).lstrip("\n"),
        path=path,
    )


def render_card(card: Card) -> str:
    meta: dict[str, Any] = {
        "id": card.id,
        "title": card.title,
        "tags": card.tags,
        "projects": card.projects,
        "links": card.links,
        "secure": card.secure,
        "updated": card.updated or date.today().isoformat(),
    }
    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    body = card.body.strip() + "\n"
    return f"---\n{fm}\n---\n\n{body}"


def card_path(root: Path, slug: str, *, secure: bool) -> Path:
    slug = validate_slug(slug)
    if secure:
        return safe_join(root, "secure", f"{slug}.md.enc")
    return safe_join(root, "cards", f"{slug}.md")


def list_card_meta(root: Path) -> list[dict[str, Any]]:
    """Metadata for index: plaintext cards + secure (decrypt once per reindex when unlocked)."""
    items: list[dict[str, Any]] = []
    cards_dir = root / "cards"
    if cards_dir.is_dir():
        for p in sorted(cards_dir.glob("*.md")):
            try:
                card = parse_card(p.read_text(encoding="utf-8"), path=p, secure=False)
                items.append(_meta(card))
            except Exception:
                continue
    secure_dir = root / "secure"
    if secure_dir.is_dir():
        key = None
        try:
            if is_unlocked():
                key = get_session_key()
        except LockedError:
            key = None
        for p in sorted(secure_dir.glob("*.md.enc")):
            slug = p.name[: -len(".md.enc")]
            try:
                slug = validate_slug(slug)
            except Exception:
                continue
            if key is not None:
                try:
                    raw = decrypt(p.read_bytes(), key)
                    card = parse_card(raw.decode("utf-8"), path=p, secure=True)
                    items.append(_meta(card))
                    continue
                except Exception:
                    pass
            items.append(
                {
                    "id": slug,
                    "title": slug,
                    "tags": [],
                    "tldr": "[secure — unlock to view]",
                    "links": [],
                    "secure": True,
                }
            )
    return items


def _meta(card: Card) -> dict[str, Any]:
    return {
        "id": card.id,
        "title": card.title,
        "tags": card.tags,
        "tldr": card.tldr,
        "links": card.links,
        "secure": card.secure,
        "projects": card.projects,
        "updated": card.updated,
    }


def read_card(root: Path, slug: str) -> Card:
    slug = validate_slug(slug)
    plain = card_path(root, slug, secure=False)
    enc = card_path(root, slug, secure=True)
    if plain.is_file():
        return parse_card(plain.read_text(encoding="utf-8"), path=plain, secure=False)
    if enc.is_file():
        try:
            key = get_session_key()
        except LockedError:
            raise LockedError(f"Card '{slug}' is secure and vault is locked") from None
        raw = decrypt(enc.read_bytes(), key)
        return parse_card(raw.decode("utf-8"), path=enc, secure=True)
    raise NotFoundError(f"Card not found: {slug}")


def write_card(root: Path, card: Card) -> Path:
    card.id = validate_slug(card.id)
    card.updated = date.today().isoformat()
    text = render_card(card)
    if card.secure:
        key = get_session_key()
        path = card_path(root, card.id, secure=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, encrypt(text.encode("utf-8"), key), mode=0o600)
        # Ensure no plaintext leftover
        plain = card_path(root, card.id, secure=False)
        if plain.is_file():
            plain.unlink()
        _log_write(root, card.id)
        return path
    path = card_path(root, card.id, secure=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text, mode=0o644)
    enc = card_path(root, card.id, secure=True)
    if enc.is_file():
        enc.unlink()
    _log_write(root, card.id)
    return path


def _log_write(root: Path, slug: str) -> None:
    try:
        from brain.stats import log_activity

        log_activity(root, "write", slug=slug)
    except Exception:
        pass


def add_link(root: Path, a: str, b: str) -> None:
    a, b = validate_slug(a), validate_slug(b)
    if a == b:
        raise VaultError("Cannot link a card to itself")
    ca, cb = read_card(root, a), read_card(root, b)
    if b not in ca.links:
        ca.links.append(b)
    if a not in cb.links:
        cb.links.append(a)
    write_card(root, ca)
    write_card(root, cb)
    try:
        from brain.stats import log_activity

        log_activity(root, "link", slug=f"{a}↔{b}")
    except Exception:
        pass


def remove_link(root: Path, a: str, b: str) -> None:
    a, b = validate_slug(a), validate_slug(b)
    if a == b:
        raise VaultError("Cannot unlink a card from itself")
    ca, cb = read_card(root, a), read_card(root, b)
    ca.links = [x for x in ca.links if x != b]
    cb.links = [x for x in cb.links if x != a]
    write_card(root, ca)
    write_card(root, cb)
    try:
        from brain.stats import log_activity

        log_activity(root, "unlink", slug=f"{a}↔{b}")
    except Exception:
        pass
