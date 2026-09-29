"""Argon2id + AES-256-GCM for secure/ cards. Fail-closed."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from brain.errors import CryptoError

MAGIC = b"BRN1"
SALT_LEN = 16
NONCE_LEN = 12
KEY_LEN = 32
# Moderate params: interactive unlock, not hashcat bait for notebook
ARGON2_TIME = 3
ARGON2_MEMORY_KIB = 64 * 1024  # 64 MiB
ARGON2_PARALLELISM = 2


def generate_salt() -> bytes:
    return secrets.token_bytes(SALT_LEN)


def derive_key(password: str, salt: bytes) -> bytes:
    if not password:
        raise CryptoError("Password is empty")
    if len(salt) != SALT_LEN:
        raise CryptoError("Invalid salt length")
    try:
        return hash_secret_raw(
            secret=password.encode("utf-8"),
            salt=salt,
            time_cost=ARGON2_TIME,
            memory_cost=ARGON2_MEMORY_KIB,
            parallelism=ARGON2_PARALLELISM,
            hash_len=KEY_LEN,
            type=Type.ID,
        )
    except Exception as e:
        raise CryptoError(f"Key derivation failed: {e}") from e


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    if len(key) != KEY_LEN:
        raise CryptoError("Invalid key length")
    nonce = secrets.token_bytes(NONCE_LEN)
    aes = AESGCM(key)
    ct = aes.encrypt(nonce, plaintext, None)
    return MAGIC + nonce + ct


def decrypt(blob: bytes, key: bytes) -> bytes:
    if len(key) != KEY_LEN:
        raise CryptoError("Invalid key length")
    if len(blob) < len(MAGIC) + NONCE_LEN + 16:
        raise CryptoError("Ciphertext too short or corrupted")
    if not blob.startswith(MAGIC):
        raise CryptoError("Unknown ciphertext format")
    nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_LEN]
    ct = blob[len(MAGIC) + NONCE_LEN :]
    aes = AESGCM(key)
    try:
        return aes.decrypt(nonce, ct, None)
    except Exception as e:
        raise CryptoError("Decryption failed (wrong password or tampered data)") from e


@dataclass
class CryptoSession:
    key: bytes
    expires_at: float  # epoch seconds

    def alive(self, now: float | None = None) -> bool:
        import time

        t = time.time() if now is None else now
        return t < self.expires_at

    def clear(self) -> None:
        # Best-effort overwrite
        if self.key:
            mutable = bytearray(self.key)
            for i in range(len(mutable)):
                mutable[i] = 0
            self.key = bytes(mutable)
        self.expires_at = 0


def pack_session(key: bytes, expires_at: float, wrap_key: bytes) -> bytes:
    import struct

    payload = struct.pack(">d", expires_at) + key
    return encrypt(payload, wrap_key)


def unpack_session(blob: bytes, wrap_key: bytes) -> tuple[bytes, float]:
    import struct

    payload = decrypt(blob, wrap_key)
    if len(payload) != 8 + KEY_LEN:
        raise CryptoError("Invalid session payload")
    (expires_at,) = struct.unpack(">d", payload[:8])
    return payload[8:], expires_at


def machine_wrap_key() -> bytes:
    """Local wrap key: prefer macOS Keychain, else ~/.config/brain/.machine_key.

    On first Keychain-capable unlock path, migrates the file key into Keychain
    (file kept as fallback so older builds still work).
    """
    from brain.paths import atomic_write_bytes, user_config_dir

    try:
        from brain import keychain as kc

        cached = kc.get_wrap_key()
        if cached is not None and len(cached) == KEY_LEN:
            return cached
    except Exception:
        kc = None  # type: ignore[assignment]

    d = user_config_dir()
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    secret_file = d / ".machine_key"
    if not secret_file.is_file():
        atomic_write_bytes(secret_file, secrets.token_bytes(KEY_LEN), mode=0o600)
    raw = secret_file.read_bytes()
    if len(raw) != KEY_LEN:
        raise CryptoError("Corrupt machine key file")

    if kc is not None:
        try:
            kc.set_wrap_key(raw)
        except Exception:
            pass
    return raw
