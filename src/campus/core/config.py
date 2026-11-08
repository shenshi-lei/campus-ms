"""应用配置：全部来自环境变量或 .env。"""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-only-change-me-please-0123456789"
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """运行期配置。环境变量名大小写不敏感，例如 ``DATABASE_URL``。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Campus Management System"
    app_env: str = "dev"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./campus.db"
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的来源配置解析为列表。"""
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @model_validator(mode="after")
    def _check_secret(self) -> Settings:
        if self.app_env in {"dev", "test"}:
            return self
        if self.jwt_secret == DEFAULT_JWT_SECRET or len(self.jwt_secret) < MIN_SECRET_LENGTH:
            raise ValueError("非开发环境必须设置至少 32 位且不同于默认值的 JWT_SECRET")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回进程内单例配置。"""
    return Settings()
