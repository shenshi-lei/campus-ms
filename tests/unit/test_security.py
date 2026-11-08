from __future__ import annotations

import jwt
import pytest

from campus.core.config import Settings
from campus.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_irreversible_and_verifiable() -> None:
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed) is True
    assert verify_password("wrong123", hashed) is False


def test_access_token_roundtrip() -> None:
    settings = Settings(app_env="test", jwt_secret="unit-test-secret-value-0123456789012345")
    token = create_access_token(7, "teacher", settings)
    payload = decode_access_token(token, settings)
    assert payload["sub"] == "7"
    assert payload["role"] == "teacher"


def test_access_token_rejects_other_secret() -> None:
    settings = Settings(app_env="test", jwt_secret="unit-test-secret-value-0123456789012345")
    other = Settings(app_env="test", jwt_secret="another-secret-value-0123456789012345")
    token = create_access_token(1, "admin", settings)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token, other)
