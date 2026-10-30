"""v0.4.4 W4：serve 是启动器不是库——除入口外任何模块不得 import serve。

AST 扫描 `src/aris/`：`import aris.serve` / `from ..serve import ...` 一律视为违例；
只允许 `serve/` 自身与入口 `cli.py`（测试是本文件的宿主，不在扫描范围）。
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src" / "aris"


def _module_name(rel: Path) -> str:
    """文件 → 绝对模块名（`__init__.py` 归到包名）。"""
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(["aris", *parts])


def _absolute_target(module: str, node: ast.ImportFrom, *, is_package: bool) -> str | None:
    """把 ImportFrom 解析成绝对模块名（相对导入按模块所在包展开）。"""
    if node.level == 0:
        return node.module
    package = module.split(".") if is_package else module.split(".")[:-1]
    drop = node.level - 1
    base = package[: len(package) - drop] if drop else package
    if not node.module:
        return ".".join(base)
    return ".".join([*base, node.module])


def _is_serve(absolute: str | None) -> bool:
    return absolute == "aris.serve" or bool(absolute and absolute.startswith("aris.serve."))


def _scan(rel: Path, module: str, tree: ast.AST) -> list[str]:
    """扫一棵 AST，返回违例行（相对路径 + 行号 + import 形态）。"""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            absolute = _absolute_target(module, node, is_package=rel.name == "__init__.py")
            if _is_serve(absolute):
                found.append(f"{rel}:{node.lineno} → from {absolute} import ...")
            elif absolute == "aris":
                found.extend(
                    f"{rel}:{node.lineno} → from aris import {alias.name}"
                    for alias in node.names
                    if alias.name == "serve"
                )
        elif isinstance(node, ast.Import):
            found.extend(
                f"{rel}:{node.lineno} → import {alias.name}"
                for alias in node.names
                if alias.name == "aris.serve" or alias.name.startswith("aris.serve.")
            )
    return found


def _violations() -> list[str]:
    found: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_SRC)
        if rel.parts[0] == "serve" or rel.as_posix() == "cli.py":
            continue  # 启动器自身与 CLI 入口例外（AGENTS.md §6）
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found.extend(_scan(rel, _module_name(rel), tree))
    return found


def test_no_module_imports_serve() -> None:
    """除 serve/ 与 cli.py 外，任何模块都不得 import serve（运行期单例归 behavior）。"""
    assert _violations() == []


def test_detector_matches_relative_import() -> None:
    """守卫本身要能命中相对导入（避免扫描逻辑写错后静默通过）。"""
    found = _scan(Path("chat/session.py"), "aris.chat.session", ast.parse("from ..serve import x"))
    assert found


def test_detector_matches_absolute_import() -> None:
    found = _scan(Path("webui/app.py"), "aris.webui.app", ast.parse("import aris.serve"))
    assert found


def test_detector_matches_package_level_import() -> None:
    """`aris/__init__.py` 的 `from . import serve` 同样算违例。"""
    found = _scan(Path("__init__.py"), "aris", ast.parse("from . import serve"))
    assert found


def test_detector_ignores_unrelated_imports() -> None:
    """别把 `serve` 之外的模块误判（例如 behavior / core）。"""
    found = _scan(
        Path("chat/session.py"),
        "aris.chat.session",
        ast.parse(
            "from ..behavior import BehaviorRuntime\nfrom ..core import call\nimport aris.settings"
        ),
    )
    assert found == []
