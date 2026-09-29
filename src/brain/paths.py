"""Path validation and user/vault config locations."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from brain.errors import PathValidationError

VAULT_MARKER = ".brain-vault"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def user_config_dir() -> Path:
    override = os.environ.get("BRAIN_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser().resolve() / "brain"
    return Path.home() / ".config" / "brain"


def user_config_path() -> Path:
    return user_config_dir() / "config.yaml"


def session_path() -> Path:
    return user_config_dir() / "session.bin"


def validate_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not SLUG_RE.match(s):
        raise PathValidationError(
            f"Invalid slug '{slug}': use lowercase letters, digits, hyphens "
            f"(max 64, must start with alnum)"
        )
    return s


def validate_root_path(raw: str | Path, *, must_exist: bool = False) -> Path:
    if raw is None or str(raw).strip() == "":
        raise PathValidationError("Path is empty")
    p = Path(str(raw)).expanduser()
    if not p.is_absolute():
        raise PathValidationError(f"Path must be absolute: {raw}")
    # Reject obvious traversal tricks in the string before resolve
    parts = p.parts
    if ".." in parts:
        raise PathValidationError("Path must not contain '..'")
    try:
        resolved = p.resolve(strict=False)
    except OSError as e:
        raise PathValidationError(f"Cannot resolve path: {e}") from e
    if must_exist and not resolved.exists():
        raise PathValidationError(f"Path does not exist: {resolved}")
    if resolved.exists() and not resolved.is_dir():
        raise PathValidationError(f"Path is not a directory: {resolved}")
    return resolved


def is_vault(path: Path) -> bool:
    return (path / VAULT_MARKER).is_file() or (path / "BRAIN.md").is_file()


def require_vault(path: Path) -> Path:
    root = validate_root_path(path, must_exist=True)
    if not is_vault(root):
        raise PathValidationError(
            f"Not a brain vault (missing {VAULT_MARKER} or BRAIN.md): {root}"
        )
    return root


def safe_join(root: Path, *parts: str) -> Path:
    """Join under root; reject escapes."""
    candidate = root.joinpath(*parts).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as e:
        raise PathValidationError("Path escapes vault root") from e
    return candidate


def atomic_write_text(path: Path, content: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".yaml")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".bin")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        tmp.replace(path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
