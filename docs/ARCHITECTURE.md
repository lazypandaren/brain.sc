# Architecture

## Components

- **Vault** — Markdown tree on disk (Google Drive sync). Marker `.brain-vault`.
- **User config** — `~/.config/brain/config.yaml` stores `root` path (CLI + UI).
- **CLI** — `brain` (`src/brain/cli.py`): search/get/add/link/lock/unlock/ui/doctor.
- **UI** — localhost force-directed graph (`ui/` + `ui_server.py`), bind `127.0.0.1` only.
- **Index** — `index/search.json` rebuilt on mutate/reindex; agent reads few cards via search.

## Card format

YAML frontmatter + `# TL;DR` + optional `## Details`. Slug: `^[a-z0-9][a-z0-9-]{0,63}$`.

## Data flow

1. Resolve root: `--root` > `BRAIN_ROOT` > user config.
2. Search loads `search.json` (no full-tree scan).
3. Secure cards: AES-GCM blobs in `secure/`; plaintext only after session unlock.

## Version

Vault `config.yaml` field `version: 1`. Bump + migrate when format changes.
