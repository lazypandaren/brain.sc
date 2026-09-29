# CLAUDE.md — Knowledge Brain

Instructions for Claude Code / Claude-based agents. Canonical rules: `docs/PROTOCOL.md`.  
Codex/Cursor-oriented twin: `AGENTS.md`. Model matrix: `docs/MODELS.md`.

## Role

You help maintain a **token-efficient knowledge brain**: find facts via search, not by dumping the vault.

## Mandatory retrieval habit

When the user asks about something that may be stored long-term:

1. Prefer tools/CLI: `brain search "…"`.
2. Then `brain get <slug>` for ≤3 hits — use TL;DR first.
3. Only request `--full` / Details if TL;DR is insufficient.
4. Refuse to bulk-read `_raw/` or decrypt `secure/*.enc`. Never solicit the master password in chat.
5. `brain status`: if `ui_running=False` → tell the user to start Brain (`brain ui` / Brain.app / `brain autostart on`).

## If vault path missing

Say clearly in the user’s language (example in English):

> Set the absolute vault path: `brain init /path` or Settings in `brain ui`.

## Writing back knowledge

User may forget to save — treat write-back as **your** job to propose, not theirs to remember.

1. Mid-session durable fact → `brain active --set "…"` (scratch note).
2. Do **not** silently `brain add` / `brain remember` unless the user asked to write.
3. When wrapping useful work → **always ask** (user’s language): save to Brain? Offer a ready draft: `brain add <slug> --tldr "…"` (TL;DR ≤5 lines) and/or one-line `brain remember`.
4. On yes → write; optional `brain recipe run after-session`. No large essays in the vault.

## Security boundaries

- Plaintext cards are searchable; sensitive material → `--secure` only after local unlock.
- No secrets in commit messages, logs, or this instruction file.

## Project pointers

- CLI package: this repo (`python -m brain` / `brain`)
- Project-local tickets stay in each project’s `docs/`; Brain holds cross-project reusable facts.
