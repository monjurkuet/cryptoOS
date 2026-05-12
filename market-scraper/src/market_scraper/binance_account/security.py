"""Encryption helpers for saved Binance credentials."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from market_scraper.core.config import Settings


class CredentialCipher:
    """Symmetric encryption wrapper for Binance API credentials."""

    def __init__(self, encryption_key: str) -> None:
        """Initialize the cipher from a Fernet key."""
        self._fernet = Fernet(encryption_key.encode("utf-8"))

    @classmethod
    def from_settings(cls, settings: Settings) -> CredentialCipher:
        """Create a cipher from application settings."""
        key = settings.binance_account.encryption_key
        if not key:
            raise RuntimeError("BINANCE_CREDENTIAL_ENCRYPTION_KEY is required")
        return cls(key)

    def encrypt(self, value: str) -> str:
        """Encrypt a plaintext credential value."""
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted_value: str) -> str:
        """Decrypt a stored credential value."""
        try:
            return self._fernet.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError("Saved Binance credentials cannot be decrypted") from exc


def mask_api_key(api_key: str) -> str:
    """Return a display-safe API key mask."""
    stripped = api_key.strip()
    if len(stripped) <= 8:
        return "****"
    return f"{stripped[:4]}...{stripped[-4:]}"
