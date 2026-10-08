# Brain (global snippet for Codex)

When recalling durable cross-project facts, use Knowledge Brain:

1. `brain search <q>` → at most 3× `brain get <slug>` (TL;DR).
2. **Hubs:** tag `hub` = entry point (not graph degree). `brain hub list` / `brain hub suggest "<keywords>"` before write-back; `brain add … --hub auto`.
3. Never read `secure/*.enc` / `_raw/`; never ask for the master password.
4. If unset root: user runs `brain init|set-root <abs>` or `brain ui` Settings.
5. `brain status`: if `ui_running=False` → tell user to start Brain (`brain ui` / Brain.app / `brain autostart on`).
6. **Write-back:** mid-session durable fact → `brain active --set "…"`. Do not silently save. When wrapping useful work → always ask: save via `brain add` / `brain remember`? (user may forget). Offer hub suggest.

Repo: `~/Documents/projects/brain-tools` (`AGENTS.md`, `docs/PROTOCOL.md`).
