# Agent protocol (token economy)

Applies to **all models/tools** (Cursor, Codex, Claude, …).  
Adapters: `AGENTS.md`, `CLAUDE.md`, Cursor skill — see `docs/MODELS.md`.  
Why MD catalog wins: `docs/TOKENS.md`. Automations patterns: `docs/AUTOMATIONS.md`.

1. If long-term knowledge may help → do not dump the vault.
2. Read `BRAIN.md` + prefer **`index/catalog.md`** or `brain search <q>` (not a full `cards/` scan).
3. Open at most **1–3** cards; prefer TL;DR (`brain get`, not `--full` unless needed).
4. Never read `_raw/` or `secure/*.enc`. Never ask for the master password in chat.
5. If root unset → ask user to `brain init|set-root` or UI Settings.
6. **UI availability:** `brain status` → if `ui_running=False`, tell the user to start Brain (`brain ui` / Brain.app / `brain autostart on`).
7. **Write-back (do not rely on user memory):**
   - Mid-session durable fact → `brain active --set "…"` (short scratch line; not a full card yet).
   - Do **not** silently `brain add` / `brain remember` unless the user said to write.
   - When wrapping useful work (or end of session) → **always ask** in the user’s language: save to Brain? Offer a ready draft (slug + TL;DR ≤5 lines) and/or one-line `brain remember`. On yes → write; on no → leave `active` as-is.
   - Optional hygiene: `brain recipe run after-session`.
8. **After-task learning** (`after-task-learning`): wrap meaningful work with 3–7 fundamental theses (what / why / how to verify / trap / next time) — learning aid, not a chat log.
9. Hygiene → `brain recipe run nightly-hygiene` (reindex + doctor).
10. Upgrade tooling (no vault wipe): `brain upgrade --pkg BrainTools-….pkg` or `./scripts/macos/upgrade.sh`.

Install global snippets: `brain agents install` (Codex + Claude + Cursor).
