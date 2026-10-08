# Brain (global snippet for Claude)

Token-efficient Knowledge Brain retrieval:

1. `brain search` → ≤3 `brain get` (TL;DR first).
2. **Hubs ≠ degree:** prefer tagged hubs (`brain hub list` / `suggest`). New cards: `brain add … --hub auto` when aliases match.
3. Never read `secure/*.enc` or `_raw/`; never ask for the master password — user unlocks locally.
4. Unset root → `brain init|set-root` / UI Settings.
5. `ui_running=False` → tell user to start Brain (`brain ui` / Brain.app / `brain autostart on`).
6. Write-back: `brain active` scratch; at wrap-up **always ask** to save (`brain add` / `brain remember` + hub).

Full protocol: brain-tools `CLAUDE.md` / `docs/PROTOCOL.md`.
