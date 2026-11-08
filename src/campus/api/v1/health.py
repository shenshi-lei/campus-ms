"""健康检查。"""

from __future__ import annotations

from fastapi import APIRouter

from campus import __version__

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    """存活探针。"""
    return {"status": "ok", "version": __version__}
