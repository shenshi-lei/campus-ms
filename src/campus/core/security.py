"""密码哈希与 JWT 令牌。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from campus.core.config import Settings

_hasher = PasswordHash.recommended()

TOKEN_TYPE = "bearer"


def hash_password(password: str) -> str:
    """使用 Argon2 生成不可逆密码哈希。"""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return _hasher.verify(password, password_hash)


def create_access_token(subject: int, role: str, settings: Settings) -> str:
    """签发访问令牌，``sub`` 为用户 ID。"""
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "type": TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """解码并校验令牌签名与有效期，失败时抛出 ``jwt.PyJWTError``。"""
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "role"]},
    )
    return dict(payload)
