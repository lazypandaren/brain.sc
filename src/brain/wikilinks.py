"""Obsidian-style wiki-links: [[slug]], [[slug|alias]], [[Title Case]]."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from brain.errors import PathValidationError
from brain.paths import validate_slug

# [[target]] or [[target|display]] — target may be slug or free title
WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+))?\]\]")

_TRANSLIT = {
    ord(a): b
    for a, b in {
        "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e",
        "є": "ie", "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i",
        "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
        "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
        "ш": "sh", "щ": "shch", "ь": "", "ъ": "", "ы": "y", "э": "e",
        "ю": "iu", "я": "ia",
    }.items()
}


def _slugify_title(name: str) -> str:
    s = name.strip().lower().translate(_TRANSLIT)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9-]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:64] or "note"


def normalize_wikilink_target(raw: str) -> str | None:
    """Turn a wiki-link target into a Brain slug, or None if empty."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return validate_slug(text)
    except PathValidationError:
        pass
    s = _slugify_title(text)
    if not s:
        return None
    try:
        return validate_slug(s)
    except PathValidationError:
        return None


def extract_wikilink_slugs(text: str) -> list[str]:
    """Ordered unique slugs from [[…]] in Markdown body."""
    seen: set[str] = set()
    out: list[str] = []
    for m in WIKILINK_RE.finditer(text or ""):
        slug = normalize_wikilink_target(m.group(1))
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
    return out


def merge_link_lists(*lists: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for lst in lists:
        for item in lst or []:
            try:
                s = validate_slug(str(item))
            except PathValidationError:
                continue
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def body_has_wikilink(body: str, slug: str) -> bool:
    slug = validate_slug(slug)
    for m in WIKILINK_RE.finditer(body or ""):
        if normalize_wikilink_target(m.group(1)) == slug:
            return True
    return False


def ensure_wikilink(body: str, slug: str) -> str:
    """Append a wiki-link line if the slug is not already linked in the body."""
    slug = validate_slug(slug)
    if body_has_wikilink(body, slug):
        return body
    body = (body or "").rstrip()
    addition = f"\n\n[[{slug}]]\n"
    return body + addition if body else f"[[{slug}]]\n"
