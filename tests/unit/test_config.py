from __future__ import annotations

import pytest
from pydantic import ValidationError

from campus.core.config import Settings
from campus.core.exceptions import NotFoundError


def test_production_requires_strong_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="prod", jwt_secret="short-secret")

    strong = Settings(app_env="prod", jwt_secret="0123456789012345678901234567890123456789")
    assert strong.app_env == "prod"


def test_cors_origin_list_parsing() -> None:
    settings = Settings(app_env="test", cors_origins=" http://a.example , http://b.example , ")
    assert settings.cors_origin_list == ["http://a.example", "http://b.example"]


def test_app_error_payload() -> None:
    error = NotFoundError("课程不存在")
    payload = error.to_payload()
    assert payload["code"] == "NOT_FOUND"
    assert payload["message"] == "课程不存在"
    assert payload["details"] == []
    assert error.status_code == 404


def test_app_error_details() -> None:
    error = NotFoundError(details=[{"loc": ["id"], "msg": "bad"}])
    assert error.message == "资源不存在"
    assert error.to_payload()["details"] == [{"loc": ["id"], "msg": "bad"}]
