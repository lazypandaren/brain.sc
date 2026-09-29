# AGENTS.md — Knowledge Brain (Codex / multi-agent)

Keep this file short. Full protocol: `docs/PROTOCOL.md`.

## What this repo is

Cross-device knowledge vault tooling: Markdown cards + CLI `brain` + localhost neural UI.  
User data lives in a separate vault folder (often Google Drive). Config: `~/.config/brain/config.yaml`.

## Before answering from “memory”

1. Run `brain search <query>` or read vault `BRAIN.md` + `core/active.md`.
2. Open at most **1–3** cards: `brain get <slug>` (TL;DR only unless details required).
3. Do **not** scan `cards/`, `secure/`, or `_raw/` wholesale.
4. Do **not** read `secure/*.enc`. Do **not** ask for the master password — tell the user to run `brain unlock` or UI Unlock locally.
5. If root is unset: `brain init <abs-path>` / `brain set-root <abs-path>` / UI Settings.
6. `brain status`: if `ui_running=False` → tell user to start Brain (`brain ui` / Brain.app / `brain autostart on`).

## Writing back (mandatory habit)

User may forget — **you** must surface the save decision.

1. Mid-session durable fact → `brain active --set "short scratch"` (scratch note).
2. Do **not** auto-write cards/memory unless the user asked to save.
3. When wrapping useful work → **always ask** (user’s language): save to Brain? Offer draft `brain add <slug> --tldr "…"` and/or `brain remember "…"`.
4. On yes → write; then optional `brain recipe run after-session`.

## Commands

```bash
brain path | status | doctor
brain search <q>
brain get <slug>
brain active --set "…"
brain add <slug> --tldr "..."
brain remember "…"
brain ui | brain autostart on
brain upgrade --pkg …
brain stats
```

## Security

- Secrets only in `secure/` after unlock.
- Never commit passwords, PEM, or plaintext secrets.
- UI must stay on `127.0.0.1`.

## Docs map

| Need | File |
|------|------|
| Token protocol | `docs/PROTOCOL.md` |
| Architecture | `docs/ARCHITECTURE.md` |
| Security | `docs/SECURITY.md` |
| Model adapters | `docs/MODELS.md` |
| Claude-oriented | `CLAUDE.md` |
