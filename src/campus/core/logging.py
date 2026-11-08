"""日志初始化。"""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """配置根日志器；重复调用是幂等的。"""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("campus").setLevel(numeric_level)
