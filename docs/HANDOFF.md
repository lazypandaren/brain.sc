# Handoff

## Repo

- Public source: https://github.com/lazypandaren/brain.sc
- Default branch: `main` (protected; PR workflow)
- Version line: `0.3.x`

## Local machine notes

- Install root: `/usr/local/lib/brain-tools`
- CLI: `/usr/local/bin/brain`
- App: `/Applications/Brain.app`
- User config: `~/.config/brain/config.yaml`
- Vault: user-chosen absolute path (often Google Drive) — **not** in this git repo

## After pulling 0.3

```bash
PYTHONPATH=src pytest -q
brain doctor
```

Upgrade packaged installs with `brain upgrade --pkg …` (vault untouched).

## Do not

- Commit vault cards or `secure/*.enc`
- Force-push `main`
- Paste master passwords into issues/PRs
