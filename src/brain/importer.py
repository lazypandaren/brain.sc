"""Import a folder of .md files as cards."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from brain.cards import Card, FRONTMATTER_RE, list_card_meta, write_card
from brain.errors import PathValidationError
from brain.index import rebuild_index
from brain.paths import validate_root_path

MAX_FILES = 500
MAX_FILE_BYTES = 512 * 1024

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


def slugify(name: str) -> str:
    s = name.strip().lower().translate(_TRANSLIT)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9-]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:64] or "note"


def _title_and_body(text: str, fallback_title: str) -> tuple[str, str]:
    # Strip existing frontmatter if present
    m = FRONTMATTER_RE.match(text)
    if m:
        text = m.group(2)
    text = text.strip()

    title = fallback_title
    heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if heading:
        title = heading.group(1).strip()[:120]

    # Ensure a TL;DR section exists for token-cheap reads
    if not re.search(r"^#\s*TL;DR", text, re.MULTILINE | re.IGNORECASE):
        first_para = ""
        for block in text.split("\n\n"):
            candidate = block.strip()
            if candidate and not candidate.startswith("#"):
                first_para = re.sub(r"\s+", " ", candidate)[:300]
                break
        tldr = first_para or title
        text = f"# TL;DR\n{tldr}\n\n## Details\n\n{text}\n"
    return title, text


def import_folder(
    root: Path, folder: str | Path, *, tag: str = "imported"
) -> dict[str, Any]:
    src = validate_root_path(folder, must_exist=True)
    if not src.is_dir():
        raise PathValidationError(f"Not a directory: {src}")

    files = sorted(p for p in src.rglob("*.md") if p.is_file())[:MAX_FILES]
    existing = {c["id"] for c in list_card_meta(root)}
    imported: list[str] = []
    skipped: list[str] = []

    for f in files:
        try:
            if f.stat().st_size > MAX_FILE_BYTES:
                skipped.append(f"{f.name} (too large)")
                continue
            raw = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped.append(f"{f.name} (unreadable)")
            continue

        base = slugify(f.stem)
        slug, i = base, 2
        while slug in existing:
            slug = f"{base}-{i}"
            i += 1

        title, body = _title_and_body(raw, f.stem)
        card = Card(id=slug, title=title, tags=[tag], body=body)
        write_card(root, card)
        existing.add(slug)
        imported.append(slug)

    rebuild_index(root)
    return {"imported": imported, "skipped": skipped, "count": len(imported)}


def import_topics(
    root: Path,
    folder: str | Path,
    *,
    tag: str = "elseveir-topic",
    skip_existing: bool = True,
) -> dict[str, Any]:
    """Import topic notes as summary cards (TL;DR-first, not full dumps)."""
    src = validate_root_path(folder, must_exist=True)
    if not src.is_dir():
        raise PathValidationError(f"Not a directory: {src}")

    files = sorted(p for p in src.glob("*.md") if p.is_file())[:MAX_FILES]
    existing = {c["id"] for c in list_card_meta(root)}
    imported: list[str] = []
    skipped: list[str] = []

    for f in files:
        try:
            if f.stat().st_size > MAX_FILE_BYTES:
                skipped.append(f"{f.name} (too large)")
                continue
            raw = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            skipped.append(f"{f.name} (unreadable)")
            continue

        base = slugify(f.stem)
        if skip_existing and base in existing:
            skipped.append(f"{base} (exists)")
            continue

        slug, i = base, 2
        while slug in existing:
            slug = f"{base}-{i}"
            i += 1

        title, body = _title_and_body(raw, f.stem)
        body = _summary_body(body, title)
        card = Card(
            id=slug,
            title=title,
            tags=[tag],
            projects=["elseveir"],
            body=body,
        )
        write_card(root, card)
        existing.add(slug)
        imported.append(slug)

    rebuild_index(root)
    return {"imported": imported, "skipped": skipped, "count": len(imported)}


def _summary_body(body: str, title: str) -> str:
    """Keep TL;DR and a short Details block (≤ ~1200 chars of details)."""
    m = re.search(
        r"(#\s*TL;DR\s*\n.*?)(?=^#\s|\Z)", body, re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    tldr_block = m.group(1).strip() if m else f"# TL;DR\n{title}\n"
    details = body
    if m:
        details = body[m.end() :].strip()
    details = re.sub(r"^#\s*Details\s*\n?", "", details, count=1, flags=re.IGNORECASE).strip()
    if len(details) > 1200:
        details = details[:1197].rstrip() + "..."
    return f"{tldr_block}\n\n## Details\n\n{details}\n" if details else f"{tldr_block}\n"