import ast
import re
from pathlib import Path

# 只把「看起来像纯路径」的字符串算作硬编码：data / data/xxx（不含空格与中文）
_PATH_RE = re.compile(r"^data(?:/[A-Za-z0-9_.-]+)+/?$")


def test_no_hardcoded_data_paths():
    root = Path("src/aris")
    whitelist_names = {
        "paths.py",
        "service.py",
        "steps.py",
        "runtime.py",
        "knowledge.py",
        "fetch.py",
    }
    offenders = []
    for p in root.rglob("*.py"):
        if p.name in whitelist_names:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                s = node.value
                if s == "data" or _PATH_RE.match(s):
                    offenders.append((str(p), s))
    assert offenders == [], f"hardcoded data paths found: {offenders}"
