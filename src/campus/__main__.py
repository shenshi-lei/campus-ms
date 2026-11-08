"""``python -m campus`` 启动开发服务器。"""

from __future__ import annotations

import uvicorn


def main() -> None:
    """以热重载模式启动。"""
    uvicorn.run("campus.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
