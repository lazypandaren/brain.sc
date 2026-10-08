# Changelog

## 0.5.0

### Added
- **Hub onboarding:** `brain hub list|init|suggest`; hub template with `Aliases:` TL;DR; `brain add --hub auto|<slug>`; API `GET/POST /api/hubs`, `POST /api/hubs/suggest`
- **Agent protocol sync:** hub ≠ degree contract in Cursor/Codex/Claude snippets; `brain agents install` refreshes them
- **Sign/notarize script:** `scripts/macos/sign-and-notarize.sh` (skips cleanly without Apple credentials)
- **CI:** `.github/workflows/test.yml` + `release.yml` (build `.pkg`, optional sign, attach to GitHub Release)
- **Hot-patch:** version-agnostic `scripts/macos/hot-patch.sh`

### Changed
- Desktop Cocoa tray/lifecycle extracted to `desktop_cocoa.py` + `desktop_state.py` (review-friendly split)
- PROTOCOL / AGENTS / CLAUDE document hub aliases + `--hub auto`

## 0.4.2

### Fixed
- Desktop: Cmd+Q / Dock Quit actually quits (no more Force Quit trap); red close still hides to tray
- Desktop: Dock click restores window after hide (`applicationShouldHandleReopen`)
- Desktop: menu-bar icon uses AppIcon + in-bundle `BrainPython` so macOS attributes extras to Brain.app (`com.braintools.app`), not bare `python3.12`
- Hot-patch / launcher scripts resolve `site-packages` via `sysconfig` (Python 3.10+, not hardcoded 3.12)
- Graph: empty-hub cloud layout + null-safe filter controls (no blank graph / NPE when `filter-mode` missing)

### Changed
- `Brain.app` packaging copies runtime interpreter into `Contents/MacOS/BrainPython` and links `Contents/lib`

## 0.4.1

### Fixed
- Graph red hubs = cards with tag `hub` (not top-N by degree)
- Desktop Show handoff: run `_show_window` on AppKit main queue (fixes exit 133 after tray show)

## 0.4.0

### Added
- Obsidian-compatible `[[wiki-links]]` (merged into card `links` on parse; written on `brain link` / API link)
- Backlinks in `brain get` and `GET /api/card/…`
- Daily notes: `brain daily`, `POST /api/daily`, recipe `daily-note`
- Graph filters: hubs-only / orphans-only; Daily button in UI

### Changed
- Graph nodes include `orphan` (no inbound and no outbound links)

## 0.3.1

### Changed
- Single dependency source: `pyproject.toml` only; removed `requirements.txt` / `requirements-runtime.txt`
- macOS `build-installer.sh` vendors wheels from `[project.dependencies]`

## 0.3.0

### Added
- macOS Keychain-backed session wrap key (`brain.keychain`), with file fallback and migration
- Dashboard write-back: Remember + Add card (`POST /api/remember`, `POST /api/add`)
- `brain import-topics` and `POST /api/import-topics` for TL;DR-first topic imports
- Doctor: UI probe states (`brain_ok` / `down` / `port_busy_non_brain`), session wrap backend, stale show-request file

### Changed
- Desktop tray lifecycle patching and HTTP show handoff (carried from 0.2.5 line)
- Public docs and README in English

### Tests
- Coverage for import-topics, remember/add APIs helpers, probe_ui, wrap-key path
