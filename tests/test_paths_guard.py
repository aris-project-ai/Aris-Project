import ast
from pathlib import Path


def test_no_hardcoded_data_paths():
    root = Path("src/aris")
    whitelist_names = {
        "paths.py",
        "datadir.py",
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
                if s == "data" or (
                    s.startswith("data/") and len(s) > 5 and "/" in s and not s.isidentifier()
                ):
                    offenders.append((str(p), s))
    assert offenders == [], f"hardcoded data paths found: {offenders}"
