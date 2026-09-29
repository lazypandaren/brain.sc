# Changelog

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
