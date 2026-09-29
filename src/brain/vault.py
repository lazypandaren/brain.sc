"""Vault initialization and seed cards."""

from __future__ import annotations

from pathlib import Path

from brain.cards import Card, write_card
from brain.config import save_user_config, save_vault_config, load_user_config
from brain.crypto import generate_salt
from brain.errors import PathValidationError, VaultError
from brain.index import rebuild_index
from brain.paths import VAULT_MARKER, is_vault, validate_root_path
from brain.session import unlock
from brain.agents_install import vault_agent_files
from brain.recipes import seed_automations

BRAIN_MD = """# BRAIN — entry point (read this first)

Cross-device knowledge vault. **Do not scan the whole tree.**

## Protocol (token economy)

1. Read this file + `core/active.md` (optional: last lines of `core/memory.md`).
2. Prefer `index/catalog.md` or `brain search <query>` — never list all of `cards/`.
3. Open **at most 1–3** cards (`brain get <slug>`). Prefer TL;DR.
4. Never read `_raw/` or `secure/*.enc` (agent must not ask for master password).
5. New durable fact → `brain add`. After a session → `brain recipe run after-session`.

## Layout

- `core/` — active, projects, memory (short learnings)
- `cards/` — plaintext knowledge
- `secure/` — encrypted cards (`.md.enc`)
- `index/` — catalog.md (lean) + search.json + map
- `automations/` — recipes (Cursor Automations patterns, local)
- `inbox/` — unsorted notes
- `_raw/` — heavy / ignore

Path: `brain set-root` or UI Settings. Models: `AGENTS.md` / `CLAUDE.md`. See tooling `docs/TOKENS.md`.
"""

ACTIVE_MD = """# Active focus

Останнє оновлення: (set via `brain active`)

## Зараз

- Налаштувати шлях vault на новому пристрої (`brain init` / UI Settings)
- Додавати атомарні картки з TL;DR

## Не чіпати

- `_raw/`
- `secure/` без локального unlock
"""

PROJECTS_MD = """# Projects

| id | path | notes |
|----|------|-------|
| elseveir | (local workspace) | Tickets stay in elseveir `docs/tickets/`; put cross-project facts here |
| brain-tools | ~/Documents/projects/brain-tools | CLI + UI for this vault |
"""


def init_vault(path: str | Path, *, master_password: str | None = None) -> Path:
    root = validate_root_path(path, must_exist=False)
    root.mkdir(parents=True, exist_ok=True)
    if is_vault(root) and (root / VAULT_MARKER).is_file():
        raise VaultError(f"Already a vault: {root}")
    if not _writable(root):
        raise PathValidationError(f"No write access: {root}")

    for sub in ("core", "index", "cards", "secure", "inbox", "_raw"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "_raw" / ".gitkeep").write_text("", encoding="utf-8")
    (root / "secure" / ".gitkeep").write_text("", encoding="utf-8")
    (root / VAULT_MARKER).write_text("brain-vault-v1\n", encoding="utf-8")
    (root / "BRAIN.md").write_text(BRAIN_MD, encoding="utf-8")
    (root / "core" / "active.md").write_text(ACTIVE_MD, encoding="utf-8")
    (root / "core" / "projects.md").write_text(PROJECTS_MD, encoding="utf-8")
    for name, content in vault_agent_files().items():
        (root / name).write_text(content, encoding="utf-8")
    seed_automations(root)

    salt = generate_salt()
    save_vault_config(
        root,
        {
            "version": 1,
            "crypto": {"salt": salt.hex(), "kdf": "argon2id", "cipher": "aes-256-gcm"},
        },
    )

    cfg = load_user_config()
    cfg["root"] = str(root.resolve())
    save_user_config(cfg)

    # Seed cards (plaintext graph demo)
    how = Card(
        id="how-to-use-brain",
        title="How to use Brain",
        tags=["meta", "protocol"],
        links=["elseveir-bridge"],
        body=(
            "# TL;DR\n"
            "Search → open 1–3 cards → update active. Path via CLI or UI Settings.\n\n"
            "## Details\n"
            "Use `brain search`, `brain get`, `brain add`. Secure cards need `brain unlock`.\n"
            "Obsidian-compatible links work in bodies: [[elseveir-bridge]].\n"
            "Daily scratch: `brain daily`.\n"
        ),
    )
    bridge = Card(
        id="elseveir-bridge",
        title="Elsevier / elseveir bridge",
        tags=["elseveir", "work"],
        links=["how-to-use-brain"],
        projects=["elseveir"],
        body=(
            "# TL;DR\n"
            "Work tickets live in elseveir `docs/`; put reusable cross-project facts in this vault.\n\n"
            "## Details\n"
            "See elseveir `docs/CONTEXT.md` and `docs/topics/knowledge-brain.md`.\n"
        ),
    )
    write_card(root, how)
    write_card(root, bridge)

    if master_password:
        unlock(root, master_password, allow_init=True)
        secret = Card(
            id="secure-example",
            title="Secure card example",
            tags=["secure", "meta"],
            links=["how-to-use-brain"],
            secure=True,
            body=(
                "# TL;DR\n"
                "This card is encrypted at rest. Only available after unlock.\n\n"
                "## Details\n"
                "Replace with real secrets; never commit plaintext passwords.\n"
            ),
        )
        write_card(root, secret)

    rebuild_index(root)
    return root.resolve()


def _writable(path: Path) -> bool:
    import os

    return os.access(path, os.W_OK)
