class BrainError(Exception):
    """Base error with user-facing message."""


class ConfigError(BrainError):
    pass


class VaultError(BrainError):
    pass


class PathValidationError(BrainError):
    pass


class CryptoError(BrainError):
    pass


class LockedError(CryptoError):
    pass


class NotFoundError(BrainError):
    pass
