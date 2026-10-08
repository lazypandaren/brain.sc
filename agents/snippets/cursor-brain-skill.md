---
name: brain
description: >-
  Cross-project Knowledge Brain vault protocol for any model (Cursor, Codex,
  Claude). Use when recalling durable facts across projects, searching knowledge
  cards, brain CLI/UI, or when the user mentions brain, картотека, vault,
  AGENTS.md, CLAUDE.md, or long-term memory outside the current repo docs.
---

# Knowledge Brain

## When to use

Any question that may live in the cross-device vault (not only the current repo). Same protocol for Codex (`AGENTS.md`) and Claude (`CLAUDE.md`) — see brain-tools `docs/MODELS.md`.

## Protocol (save tokens)

1. Prefer `index/catalog.md` or `brain search <query>`; read `BRAIN.md` + `core/active.md` — never scan all cards.
2. **Hub-first:** start from `vault-map` / `context` / topic hubs (`brain hub list`). Skip UUID `imported` transcript cards unless the user asks for that chat.
3. Open at most **1–3** cards via `brain get <slug>` (TL;DR first; `--full` only if needed).
4. **Hubs ≠ degree:** tag `hub` is the intentional entry point. Graph degree/orphan filters are UI-only — never file a new card by “most linked”.
5. **Write-back + hub:** before `brain add`, run `brain hub suggest "<project keywords>"` (or `brain add … --hub auto`). Hub TL;DR must keep **Aliases:** lines so search matches without a long project essay.
6. **Split stores:** work tickets often live in a project `docs/tickets/`; the vault holds reusable cross-project facts. Do not copy ticket dumps into skills.
7. **Never** read `secure/*.enc` or `_raw/`. **Never** ask for the master password in chat; tell the user to run `brain unlock` or UI Unlock locally.
8. If root is unset: ask user to set path with `brain init <abs>` / `brain set-root <abs>` / UI Settings (Google Drive folder).
9. **UI must be findable:** run `brain status` (look for `ui_running=`). If `ui_running=False` / CLI missing → **tell the user** (their language): запусти Brain — `brain ui`, **Brain.app**, або `brain autostart on`. Do not pretend the neural UI is available.
10. **Write-back (user may forget — you must propose):**
   - Mid-session durable fact → `brain active --set "…"` (проміжна нотатка).
   - Do **not** silently `brain add` / `brain remember` unless the user asked to save.
   - When wrapping useful work → **always ask** (user’s language): чи записати в Brain? Offer draft slug + TL;DR ≤5 lines and/or `brain remember` (+ suggested hub). On yes → write; optional `brain recipe run after-session`.
11. **After-task learning (card `after-task-learning`):** after a meaningful work block, add 3–7 short fundamental theses (що / чому / як перевірити / пастка / наступний раз) so the user can learn — not a chat dump, no secrets.
12. MD catalog is the token-optimal store (see brain-tools `docs/TOKENS.md`). Recipes mirror Automations patterns locally (`docs/AUTOMATIONS.md`).

## Commands

```bash
brain path | status | doctor
brain search <q>
brain get <slug>
brain hub list | init <slug> --aliases "a,b,c" | suggest "text"
brain active --set "…"
brain add <slug> --tldr "..." [--hub auto|<slug>]
brain remember "…"
brain ui | brain desktop | brain autostart on
brain upgrade --pkg BrainTools-….pkg
brain stats
brain agents install   # Codex + Claude + Cursor (overwrites this skill)
```

Tooling: `.pkg` install → `/usr/local/lib/brain-tools`; dev repo → `~/Documents/projects/brain-tools` (its `docs/` has PROTOCOL, TOKENS, MODELS).

`brain agents install --cursor` **overwrites** this file from `agents/snippets/cursor-brain-skill.md`. Keep the snippet and this skill in sync.
