"""User config (~/.config/brain) and vault-local config."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from brain.errors import ConfigError, PathValidationError
from brain.paths import (
    atomic_write_text,
    is_vault,
    user_config_path,
    validate_root_path,
)

DEFAULT_USER_CONFIG = {
    "root": None,
    "max_cards_per_query": 3,
    "default_detail": "tldr",
    "session_ttl_minutes": 60,
    "ui_port": 8765,
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(data, dict):
        raise ConfigError(f"Config must be a mapping: {path}")
    return data


def load_user_config() -> dict[str, Any]:
    cfg = dict(DEFAULT_USER_CONFIG)
    cfg.update(_load_yaml(user_config_path()))
    return cfg


def save_user_config(cfg: dict[str, Any]) -> None:
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Never store secrets in user config
    safe = {
        "root": cfg.get("root"),
        "max_cards_per_query": int(cfg.get("max_cards_per_query", 3)),
        "default_detail": cfg.get("default_detail", "tldr"),
        "session_ttl_minutes": int(cfg.get("session_ttl_minutes", 60)),
        "ui_port": int(cfg.get("ui_port", 8765)),
    }
    atomic_write_text(path, yaml.safe_dump(safe, sort_keys=False, allow_unicode=True))


def resolve_root(cli_root: str | None = None) -> Path:
    """Priority: CLI flag > BRAIN_ROOT env > user config."""
    if cli_root:
        return validate_root_path(cli_root, must_exist=True)
    env = os.environ.get("BRAIN_ROOT")
    if env:
        return validate_root_path(env, must_exist=True)
    cfg = load_user_config()
    root = cfg.get("root")
    if not root:
        raise ConfigError(
            "Vault root not set. Use: brain init <path> | brain set-root <path> | UI Settings"
        )
    return validate_root_path(root, must_exist=True)


def set_root(path: str | Path, *, require_vault: bool = True) -> Path:
    root = validate_root_path(path, must_exist=True)
    if require_vault and not is_vault(root):
        raise PathValidationError(
            f"Not a brain vault. Run: brain init {root}"
        )
    # Writable check
    if not os.access(root, os.R_OK | os.W_OK):
        raise PathValidationError(f"No read/write access: {root}")
    cfg = load_user_config()
    cfg["root"] = str(root)
    save_user_config(cfg)
    return root


def load_vault_config(root: Path) -> dict[str, Any]:
    return _load_yaml(root / "config.yaml")


def save_vault_config(root: Path, cfg: dict[str, Any]) -> None:
    atomic_write_text(
        root / "config.yaml",
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
    )
