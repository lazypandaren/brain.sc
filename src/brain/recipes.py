"""Lean catalog + automation recipes + run memory (Automations-inspired)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from brain.cards import FRONTMATTER_RE, list_card_meta
from brain.doctor import run_doctor
from brain.errors import BrainError, NotFoundError
from brain.paths import atomic_write_text, safe_join, validate_slug


@dataclass
class Recipe:
    id: str
    title: str
    trigger: str = "manual"
    scope: str = "vault-only"
    max_cards: int = 0
    verify: str = ""
    body: str = ""
    path: Path | None = None
    steps: list[str] = field(default_factory=list)


def write_catalog(root: Path, items: list[dict[str, Any]] | None = None) -> Path:
    """Ultra-lean catalog for agents: one line per card (minimal tokens)."""
    items = items if items is not None else list_card_meta(root)
    lines = [
        "# Catalog (read this instead of scanning cards/)",
        "",
        "Format: `id` — title — tags — tldr≤120",
        "",
    ]
    for c in sorted(items, key=lambda x: x.get("id") or ""):
        tags = ",".join(c.get("tags") or [])
        tldr = re.sub(r"\s+", " ", (c.get("tldr") or ""))[:120]
        sec = " 🔒" if c.get("secure") else ""
        lines.append(f"- `{c.get('id')}`{sec} — {c.get('title')} — [{tags}] — {tldr}")
    lines.append("")
    path = root / "index" / "catalog.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, "\n".join(lines) + "\n", mode=0o644)
    return path


def remember(root: Path, note: str, *, source: str = "session") -> None:
    """Append a short learning (Automations-style memory). Keep lines tiny."""
    note = re.sub(r"\s+", " ", (note or "").strip())
    if not note:
        raise BrainError("Empty memory note")
    if len(note) > 240:
        note = note[:237] + "..."
    path = root / "core" / "memory.md"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Memory (short learnings from runs)\n\n"
            "Agents: append via `brain remember`. Do not rewrite history.\n\n",
            encoding="utf-8",
        )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"- {ts} [{source}] {note}\n")
    try:
        from brain.stats import log_activity

        log_activity(root, "remember", detail=note[:100])
    except Exception:
        pass


def parse_recipe(text: str, *, path: Path | None = None) -> Recipe:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise BrainError("Recipe missing YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise BrainError("Invalid recipe frontmatter")
    rid = validate_slug(str(meta.get("id") or (path.stem if path else "recipe")))
    body = m.group(2).lstrip("\n")
    steps = []
    for line in body.splitlines():
        s = line.strip()
        if re.match(r"^\d+\.\s+", s):
            steps.append(re.sub(r"^\d+\.\s+", "", s))
    return Recipe(
        id=rid,
        title=str(meta.get("title") or rid),
        trigger=str(meta.get("trigger") or "manual"),
        scope=str(meta.get("scope") or "vault-only"),
        max_cards=int(meta.get("max_cards") or 0),
        verify=str(meta.get("verify") or ""),
        body=body,
        path=path,
        steps=steps,
    )


def list_recipes(root: Path) -> list[Recipe]:
    d = root / "automations"
    if not d.is_dir():
        return []
    out: list[Recipe] = []
    for p in sorted(d.glob("*.md")):
        if p.name.upper() == "README.MD":
            continue
        try:
            out.append(parse_recipe(p.read_text(encoding="utf-8"), path=p))
        except Exception:
            continue
    return out


def get_recipe(root: Path, recipe_id: str) -> Recipe:
    recipe_id = validate_slug(recipe_id)
    path = safe_join(root, "automations", f"{recipe_id}.md")
    if not path.is_file():
        raise NotFoundError(f"Recipe not found: {recipe_id}")
    return parse_recipe(path.read_text(encoding="utf-8"), path=path)


def run_recipe(root: Path, recipe_id: str) -> dict[str, Any]:
    """Execute built-in safe steps; leave the rest as manual for the agent."""
    recipe = get_recipe(root, recipe_id)
    log: list[str] = []
    ran_doctor = False
    for step in recipe.steps:
        key = step.strip().lower()
        if "brain reindex" in key or key == "reindex":
            _do_reindex(root, log)
        elif "brain doctor" in key or key == "doctor":
            _do_doctor(root, log)
            ran_doctor = True
        else:
            log.append(f"manual: {step}")

    if recipe.verify == "doctor" and not ran_doctor:
        _do_doctor(root, log)

    return {
        "id": recipe.id,
        "title": recipe.title,
        "trigger": recipe.trigger,
        "scope": recipe.scope,
        "max_cards": recipe.max_cards,
        "log": log,
        "instructions": recipe.body,
    }


def _do_reindex(root: Path, log: list[str]) -> None:
    from brain.index import rebuild_index as ri

    n = len(ri(root))  # also writes catalog.md
    log.append(f"ok: reindex ({n} cards) + catalog")


def _do_doctor(root: Path, log: list[str]) -> None:
    report = run_doctor(root)
    if report.ok:
        log.append("ok: doctor")
    else:
        log.append("fail: doctor — " + "; ".join(report.issues[:5]))
        remember(root, f"recipe doctor failed: {'; '.join(report.issues[:2])}", source="recipe")


SEED_RECIPES: dict[str, str] = {
    "nightly-hygiene.md": """---
id: nightly-hygiene
title: Nightly vault hygiene
trigger: schedule
scope: vault-only
max_cards: 0
verify: doctor
---
# Instructions

1. brain reindex
2. brain doctor
3. List `inbox/` filenames only if any (do not open note bodies).
4. If doctor failed — `brain remember` one line with the failure.
""",
    "after-session.md": """---
id: after-session
title: After agent session capture
trigger: after-session
scope: vault-only
max_cards: 2
verify: ""
---
# Instructions

1. Skim `core/active.md` only.
2. If a durable fact appeared — `brain add` or update one card (TL;DR ≤5 lines).
3. `brain remember` one line: what worked / what to avoid next time.
4. brain reindex
""",
    "token-safe-answer.md": """---
id: token-safe-answer
title: Token-safe answer path
trigger: manual
scope: vault-only
max_cards: 3
verify: ""
---
# Instructions

1. Read `index/catalog.md` OR `brain search <q>` (not both fully — prefer search).
2. Open at most 3 cards via `brain get` (TL;DR only).
3. Answer. Do not load Details unless TL;DR insufficient.
4. Never touch `_raw/` or `secure/*.enc`.
""",
}


def seed_automations(root: Path) -> None:
    d = root / "automations"
    d.mkdir(parents=True, exist_ok=True)
    (d / "README.md").write_text(
        "# Automations (recipes)\n\n"
        "Inspired by Cursor Automations: trigger + instructions + verify + memory.\n"
        "Run: `brain recipe list` / `brain recipe run <id>`.\n"
        "See brain-tools `docs/AUTOMATIONS.md` and `docs/TOKENS.md`.\n",
        encoding="utf-8",
    )
    for name, content in SEED_RECIPES.items():
        p = d / name
        if not p.is_file():
            p.write_text(content, encoding="utf-8")
    mem = root / "core" / "memory.md"
    if not mem.is_file():
        mem.write_text(
            "# Memory (short learnings from runs)\n\n"
            "Agents: append via `brain remember \"…\"`. Keep each line ≤240 chars.\n\n",
            encoding="utf-8",
        )
