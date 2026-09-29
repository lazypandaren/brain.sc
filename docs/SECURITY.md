# Security

## Threat model (v0.1)

**Protect:** contents of `secure/*.md.enc` at rest on disk/Drive; master password never in git/logs.

**Out of scope:** malware with local unlocked session access; physical access while unlocked; Drive account compromise of *plaintext* `cards/` (those are intentionally searchable).

## Crypto

- KDF: Argon2id (time=3, memory=64MiB, parallelism=2)
- Cipher: AES-256-GCM, magic `BRN1`, random nonce per file
- Salt in vault `config.yaml` (not secret); verifier ciphertext proves password
- Session: key wrapped with machine-local `.machine_key` under `~/.config/brain/`, TTL from config

## UI / network

- HTTP binds **127.0.0.1 only**
- No password in access logs for `/api/unlock`
- Path traversal blocked for static files and vault joins

## Agent policy

- Never request master password in chat
- Never read `secure/*.enc` or `_raw/`
- Fail-closed: locked secure → tell user to `brain unlock` locally

## Checklist before release changes

- [ ] No plaintext secure after `add --secure` / after `lock`
- [ ] Wrong password / truncated ciphertext → CryptoError
- [ ] `brain doctor` clean on fresh init
- [ ] UI not listening on `0.0.0.0`
