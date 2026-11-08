"""导入导出契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImportRequest(BaseModel):
    """CSV 文本导入。"""

    csv: str = Field(min_length=1, max_length=200_000)
    dry_run: bool = False
    mode: str = Field(default="upsert", pattern="^(upsert|skip)$")


class ImportResult(BaseModel):
    """导入结果。"""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    preview: list[dict[str, str]] = Field(default_factory=list)
