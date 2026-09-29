# Decisions (ADR-lite)

## ADR-001: Separate vault from elseveir repo

Elsevier `docs/` stays project-local. Brain holds cross-project memory synced via Drive.

## ADR-002: Encrypt only `secure/`

Full-vault encryption breaks fast search and graph. Sensitive notes opt into `secure/`.

## ADR-003: search.json not embeddings

Deterministic, offline, cheap for agents; rebuild on write.

## ADR-004: Path in user config + UI Settings

Vault data on Drive; machine-local `~/.config/brain/config.yaml` points at mount path (differs per OS/device).

## ADR-005: Localhost UI only

No cloud UI in v0.1; reduces attack surface for unlock API.

## ADR-006: Multi-model adapters, one protocol

Canonical rules live in `docs/PROTOCOL.md`. Thin native files:

- `AGENTS.md` — Codex / AGENTS.md ecosystem
- `CLAUDE.md` — Claude Code
- Cursor skill — `~/.cursor/skills/brain/`
- Vault copies of short `AGENTS.md` / `CLAUDE.md` for Drive-opened folders

`brain agents install` merges marked snippets into `~/.codex/AGENTS.md` and `~/.claude/CLAUDE.md` so Brain works outside this repo.

## ADR-007: MD catalog over dumping chat / embeddings-first

Agent path: `catalog.md` / `brain search` → ≤3 TL;DR cards. Lowest tokens, works on Google Drive, model-agnostic.

## ADR-008: Borrow Automations patterns locally

Recipes in `automations/`, short `core/memory.md`, `verify: doctor`. Cloud Cursor Automations remain optional wiring, not a dependency.
