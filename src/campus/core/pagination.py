"""分页参数与通用辅助。"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class PageParams:
    """已校验的分页参数。"""

    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def clamp_page(page: int, page_size: int) -> PageParams:
    """把外部传入的分页参数限制到合法区间。"""
    safe_page = max(page, 1)
    safe_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return PageParams(page=safe_page, page_size=safe_size)
