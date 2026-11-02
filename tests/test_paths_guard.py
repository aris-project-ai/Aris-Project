import ast
import re
from pathlib import Path

# 数据目录只允许在 infra/paths.py 里解析；其他地方必须用 paths 的 helper 拼。
# 判定以「看起来像纯路径」为准：data/xxx（不含空格与中文），避免把 JSON 字段名
# （"data"）、报错文案（f"data/config/x.toml 缺少字段"）错判成硬编码。
_PATH_RE = re.compile(r"^data(/[A-Za-z0-9_.-]+)+/?$")
_PATH_LIKE_RE = re.compile(r"^data(/[A-Za-z0-9_.-]*)*/?$")
_ALLOWED_FILES = {"paths.py"}
_SRC = Path("src/aris")


def _docstring_ids(tree: ast.AST) -> set[int]:
    """收集文档字符串节点：docstring 里写路径属于说明文字，不算硬编码。"""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _is_path_like(text: str) -> bool:
    """data 开头且不含空格 / 中文，才算"路径"而不是说明文字。"""
    return bool(_PATH_LIKE_RE.match(text)) and text.strip() == text


def _iter_offenders(root: Path = _SRC) -> list[str]:
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in _ALLOWED_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except OSError, UnicodeError, SyntaxError:
            continue
        docs = _docstring_ids(tree)
        for node in ast.walk(tree):
            # 1) 纯路径字面量：data/xxx
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docs
                and _PATH_RE.match(node.value)
            ):
                offenders.append(f"{path}:{node.lineno}: 字面量 {node.value!r}")
                continue
            # 2) Path("data") / os.path.join("data", ...)
            if isinstance(node, ast.Call) and node.args:
                first = node.args[0]
                func = node.func
                name = getattr(func, "attr", None) or getattr(func, "id", None)
                if (
                    name in {"Path", "join"}
                    and isinstance(first, ast.Constant)
                    and first.value == "data"
                ):
                    offenders.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
                    continue
            # 3) "data" + "/logs" 之类的字符串拼接
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                left, right = node.left, node.right
                if (
                    isinstance(left, ast.Constant)
                    and left.value == "data"
                    and isinstance(right, ast.Constant)
                    and isinstance(right.value, str)
                    and right.value.startswith("/")
                ):
                    offenders.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
                    continue
            # 4) f"data/{name}"：每个字面量片段都得是路径片段
            if isinstance(node, ast.JoinedStr):
                literals = [
                    v.value
                    for v in node.values
                    if isinstance(v, ast.Constant) and isinstance(v.value, str)
                ]
                if literals and all(_is_path_like(s) for s in literals if s):
                    offenders.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
    return offenders


def test_no_hardcoded_data_paths():
    offenders = _iter_offenders()
    assert offenders == [], (
        "发现硬编码数据目录（请改用 aris.infra.paths 的 helper）:\n" + "\n".join(offenders)
    )


def test_guard_detects_known_violations(tmp_path: Path):
    """自检：确认规则真的能抓到四种写法，避免守卫形同虚设。"""
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from pathlib import Path\n"
        "import os\n"
        "A = 'data/logs'\n"
        "B = Path('data')\n"
        "C = os.path.join('data', 'logs')\n"
        "D = 'data' + '/logs'\n"
        "E = f'data/{x}'\n",
        encoding="utf-8",
    )
    offenders = _iter_offenders(tmp_path)
    assert len(offenders) == 5, offenders


def test_no_hardcoded_home_directory():
    """数据目录可自定义，安装态也不该假设固定家目录。"""
    offenders: list[str] = []
    banned = {"Path.home()", "expanduser('~')", 'expanduser("~")'}
    for path in sorted(_SRC.rglob("*.py")):
        if path.name in _ALLOWED_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                unparsed = ast.unparse(node)
                if unparsed in banned:
                    offenders.append(f"{path}:{node.lineno}: {unparsed}")
    assert offenders == [], "发现硬编码家目录:\n" + "\n".join(offenders)
