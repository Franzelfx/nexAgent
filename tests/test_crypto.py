"""Tests for the crypto service."""

from __future__ import annotations

import pytest

from nexagent.config import settings


@pytest.fixture(autouse=True)
def _ensure_encryption_key(monkeypatch):
    """Ensure encryption key is set for tests."""
    from cryptography.fernet import Fernet

    if not settings.encryption_key:
        key = Fernet.generate_key().decode()
        monkeypatch.setattr(settings, "encryption_key", key)
    # Reset cached fernet instance
    import nexagent.services.crypto as crypto_mod
    crypto_mod._fernet = None
    yield
    crypto_mod._fernet = None


def test_encrypt_decrypt_roundtrip():
    from nexagent.services.crypto import decrypt_api_key, encrypt_api_key

    plaintext = "sk-test-key-12345"
    encrypted = encrypt_api_key(plaintext)
    assert encrypted != plaintext
    assert decrypt_api_key(encrypted) == plaintext


def test_encrypted_values_differ():
    from nexagent.services.crypto import encrypt_api_key

    enc1 = encrypt_api_key("same-key")
    enc2 = encrypt_api_key("same-key")
    # Fernet tokens include a timestamp so they differ
    assert enc1 != enc2


def test_decrypt_with_wrong_data():
    from nexagent.services.crypto import decrypt_api_key

    with pytest.raises(ValueError, match="Failed to decrypt"):
        decrypt_api_key("not-a-valid-fernet-token")
