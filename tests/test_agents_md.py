from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE_BEGIN = "<!-- TREE:BEGIN -->"
TREE_END = "<!-- TREE:END -->"


def _documented_paths() -> set[str]:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    block = text.split(TREE_BEGIN)[1].split(TREE_END)[0]
    return {line.strip() for line in block.splitlines() if line.strip()}


def test_documented_paths_exist() -> None:
    documented = _documented_paths()
    assert documented, "AGENTS.md 的目录清单为空"
    missing = sorted(path for path in documented if not (ROOT / path).exists())
    assert missing == [], f"AGENTS.md 列出的路径不存在：{missing}"


def test_every_python_module_is_documented() -> None:
    documented = _documented_paths()
    actual = {
        path.relative_to(ROOT).as_posix()
        for folder in ("src", "tests", "migrations")
        for path in (ROOT / folder).rglob("*.py")
    }
    undocumented = sorted(actual - documented)
    assert undocumented == [], f"以下 Python 文件未写入 AGENTS.md 清单：{undocumented}"


def test_python_code_blocks_are_valid() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)
    assert blocks, "AGENTS.md 应至少包含一个 python 代码块"
    for index, block in enumerate(blocks, start=1):
        try:
            ast.parse(block)
        except SyntaxError as error:  # pragma: no cover - 诊断信息
            raise AssertionError(
                f"AGENTS.md 第 {index} 个 python 代码块语法错误：{error}"
            ) from error
