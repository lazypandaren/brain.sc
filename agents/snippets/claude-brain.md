# Brain (global snippet for Claude)

Cross-project memory uses the `brain` CLI / vault (see `~/Documents/projects/brain-tools`).

- Search first (`brain search`), then ≤3 cards (`brain get`), TL;DR before Details.
- Do not read encrypted `secure/*.enc` or `_raw/`; do not ask for the master password — user unlocks locally.
- Missing vault path → tell user to set it via `brain init` / `set-root` / UI Settings.
- Check `brain status` → if `ui_running=False`, tell user to start Brain (`brain ui` / Brain.app / `brain autostart on`).
- **Write-back:** mid-session → `brain active --set "…"`. Do not auto-save cards. When wrapping useful work → always ask whether to `brain add` / `brain remember` (user may forget).
- Full rules: `CLAUDE.md` and `docs/PROTOCOL.md` in brain-tools.
