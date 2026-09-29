# Multi-model adapters

Brain must be understandable to **different coding agents**, not only Cursor.

## Source of truth

| Layer | File | Purpose |
|-------|------|---------|
| Canonical protocol | [`PROTOCOL.md`](PROTOCOL.md) | Shared rules (tokens, secure, path) |
| Codex / AGENTS ecosystem | [`../AGENTS.md`](../AGENTS.md) | OpenAI Codex, many CLIs that read `AGENTS.md` |
| Claude | [`../CLAUDE.md`](../CLAUDE.md) | Claude Code / Claude-oriented sessions |
| Cursor | `~/.cursor/skills/brain/SKILL.md` | Skill trigger across projects |
| Vault entry | vault `BRAIN.md` + optional `AGENTS.md` / `CLAUDE.md` copies | Any agent that opens the Drive folder |

Keep adapters **thin**: same rules, wording tuned to how that product loads context.

## Install on a machine (best practice)

**Codex (global):** append or symlink brain rules into `~/.codex/AGENTS.md` (keep under a few KB; Codex merges with a size cap ~32KiB).

```bash
brain agents install --codex
# or manually: copy agents/snippets/codex-brain.md into ~/.codex/AGENTS.md
```

**Claude Code (global):**

```bash
brain agents install --claude
# writes/merges ~/.claude/CLAUDE.md snippet
```

**Cursor:** skill already at `~/.cursor/skills/brain/SKILL.md`.

**Per vault (Drive):** `brain init` writes `AGENTS.md` + `CLAUDE.md` into the vault so Codex/Claude opening that folder inherit protocol without this git repo.

## Style guidelines per model family

- **Codex:** imperative bullets, commands first, short `AGENTS.md`, no fluff (size budget).
- **Claude:** explicit “mandatory habit”, refusal boundaries, language preference of the user.
- **Cursor:** skill `description` must list trigger terms; protocol identical.

## Do not fork the protocol

If you change retrieval/security rules, update `PROTOCOL.md` first, then sync adapters (`brain agents sync` / this doc checklist).
