"""In-memory / disk session for unlocked master key."""

from __future__ import annotations

import time
from pathlib import Path

from brain.config import load_user_config, load_vault_config
from brain.crypto import (
    CryptoSession,
    derive_key,
    machine_wrap_key,
    pack_session,
    unpack_session,
)
from brain.errors import CryptoError, LockedError
from brain.paths import atomic_write_bytes, session_path

_memory: CryptoSession | None = None


def is_unlocked() -> bool:
    global _memory
    if _memory and _memory.alive():
        return True
    # try disk session
    try:
        get_session_key()
        return True
    except LockedError:
        return False


def unlock(root: Path, password: str, *, allow_init: bool = False) -> None:
    global _memory
    vcfg = load_vault_config(root)
    salt_hex = vcfg.get("crypto", {}).get("salt")
    if not salt_hex:
        raise CryptoError("Vault has no crypto.salt — re-init or fix config.yaml")
    salt = bytes.fromhex(salt_hex)
    key = derive_key(password, salt)
    # Verify by decrypting a canary if present
    verifier = vcfg.get("crypto", {}).get("verifier")
    from brain.crypto import decrypt, encrypt

    if verifier:
        try:
            decrypt(bytes.fromhex(verifier), key)
        except CryptoError as e:
            raise CryptoError("Wrong master password") from e
    elif allow_init:
        # First-time password setup only (CLI init / UI set-password)
        from brain.config import save_vault_config

        vcfg.setdefault("crypto", {})["verifier"] = encrypt(b"brain-ok", key).hex()
        save_vault_config(root, vcfg)
    else:
        raise CryptoError(
            "Master password not set. Use Settings → Set password, or: brain unlock after init with password"
        )

    ttl = int(load_user_config().get("session_ttl_minutes", 60))
    expires = time.time() + ttl * 60
    _memory = CryptoSession(key=key, expires_at=expires)
    wrap = machine_wrap_key()
    atomic_write_bytes(session_path(), pack_session(key, expires, wrap), mode=0o600)


def lock() -> None:
    global _memory
    if _memory:
        _memory.clear()
        _memory = None
    sp = session_path()
    if sp.is_file():
        sp.unlink(missing_ok=True)


def get_session_key() -> bytes:
    global _memory
    if _memory and _memory.alive():
        return _memory.key
    sp = session_path()
    if not sp.is_file():
        raise LockedError("Vault is locked. Run: brain unlock")
    try:
        key, expires = unpack_session(sp.read_bytes(), machine_wrap_key())
    except CryptoError as e:
        lock()
        raise LockedError("Session invalid; locked") from e
    if time.time() >= expires:
        lock()
        raise LockedError("Session expired. Run: brain unlock")
    _memory = CryptoSession(key=key, expires_at=expires)
    return key
