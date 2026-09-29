# Contributing

## Language

Repository docs, commit messages, PR descriptions, and issue text are **English**.

## Branch model

- Default branch: `main` (protected)
- Feature branches: `feat/…`, `fix/…`, `docs/…`
- Open a PR into `main`; do not force-push `main`

## Local checks

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e ".[dev]"
pytest -q
```

Dependencies live only in `pyproject.toml` (`[project.dependencies]` + `[project.optional-dependencies]`). Do not add `requirements.txt`.

## Scope

Keep PRs focused. Do not commit vault data, secrets, `.venv/`, `dist/`, or installer binaries.
