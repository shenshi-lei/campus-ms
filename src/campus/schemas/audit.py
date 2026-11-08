"""审计契约。"""

from __future__ import annotations

from datetime import datetime

from campus.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    """审计日志输出。"""

    id: int
    user_id: int | None
    username: str
    role: str
    method: str
    path: str
    status_code: int
    ip: str
    detail: str
    created_at: datetime
