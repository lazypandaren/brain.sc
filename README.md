# Knowledge Brain (`brain.sc`)

Cross-project knowledge vault: Markdown cards + CLI + local neural UI + optional encrypted `secure/` cards.

**Why it exists.** AI chats forget. Project notes scatter. Agents waste tokens re-reading everything. Brain is a durable, search-first memory you and your agents share — offline, Drive-synced, no vendor lock-in.

## Benefits

- **Token-cheap for agents** — `brain search` → ≤3 TL;DR cards instead of dumping the vault
- **Works across tools** — Cursor / Codex / Claude via one protocol (`docs/PROTOCOL.md`)
- **Secrets stay local** — encrypt only `secure/`; UI binds to `127.0.0.1`
- **Plain Markdown** — vault is files you can open in any editor in 20 years
- **Desktop tray app (macOS)** — close → menu bar; second launch shows the window

## Requirements

- Python 3.10+
- macOS recommended for Brain.app / tray (CLI + UI work on other platforms with caveats)

## Quick start (dev)

```bash
git clone https://github.com/lazypandaren/brain.sc.git
cd brain.sc
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

brain init "/absolute/path/to/your/Brain_Storage"
brain search "aws"
brain get how-to-use-brain
brain ui          # http://127.0.0.1:8765/
brain desktop     # native window + tray (needs pywebview)
brain doctor
```

Point agents at the vault:

```bash
brain agents install --all
```

## Build / install (macOS package)

See **[docs/BUILD.md](docs/BUILD.md)** for the full installer pipeline (`.pkg`, Brain.app, upgrade).

Short path:

```bash
./scripts/macos/build-installer.sh
# → dist/macos/BrainTools-<version>-<arch>.pkg
sudo installer -pkg dist/macos/BrainTools-*.pkg -target /
# or: brain upgrade --pkg /path/to/BrainTools-….pkg
```

## What’s new in 0.3.0

- Session wrap prefers **macOS Keychain** (file fallback)
- UI **write-back**: Remember + Add card from Dashboard
- **`brain import-topics`** — summary import from topic folders (e.g. project `docs/topics`)
- Doctor reports UI probe / stuck port / session wrap backend
- Desktop close→tray hardening (Cocoa lifecycle + HTTP show handoff)

## Layout

| Path | Role |
|------|------|
| `src/brain/` | CLI, vault, crypto, UI server, desktop |
| `ui/` | Neural graph frontend |
| `docs/` | Protocol, architecture, security, build |
| `scripts/macos/` | Installer / upgrade / hot-patch |
| `tests/` | Pytest suite |

User config (machine-local): `~/.config/brain/config.yaml`  
Vault data: the folder you choose (often Google Drive).

## Security

- Never commit passwords, PEMs, or plaintext secrets
- Do not read `secure/*.enc` without local unlock
- Unlock only on localhost UI / `brain unlock`

## License / contributing

Public repository. Prefer PRs against `main` (branch protection: reviews + status checks when enabled). Keep docs and user-facing repo text in **English**.
