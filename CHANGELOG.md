# Changelog

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
