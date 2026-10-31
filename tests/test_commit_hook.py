"""commit-msg hook 的回归测试（shell 层）。

覆盖 head 格式、merge/revert 放行、footer token 校验与普通正文不误伤。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / ".githooks" / "commit-msg"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="需要 sh")


def run_hook(tmp_path: Path, message: str) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(message, encoding="utf-8")
    return subprocess.run(["sh", str(HOOK), str(path)], text=True, capture_output=True)


def test_accepts_head_only(tmp_path: Path) -> None:
    assert run_hook(tmp_path, "feat(cli): 增加 info 命令\n").returncode == 0


def test_rejects_bad_head(tmp_path: Path) -> None:
    out = run_hook(tmp_path, "update stuff\n")
    assert out.returncode == 1
    assert "Conventional Commits" in out.stdout


def test_accepts_body_and_footer(tmp_path: Path) -> None:
    message = (
        "fix(paths): 修复数据目录解析\n\n"
        "- 先读 ARIS_DATA_DIR 再退回开发树\n"
        "- 补一个回归用例\n\n"
        "Refs: #42\n"
        "Co-authored-by: Morin <morin@example.com>\n"
    )
    assert run_hook(tmp_path, message).returncode == 0


def test_accepts_closes_hash_form(tmp_path: Path) -> None:
    assert run_hook(tmp_path, "fix: 修好了\n\nCloses #42\n").returncode == 0


def test_rejects_unknown_footer_line(tmp_path: Path) -> None:
    message = "fix: 修好了\n\nRefs: #42\nSigned-off-by: someone\nnot a footer\n"
    out = run_hook(tmp_path, message)
    assert out.returncode == 1
    assert "footer" in out.stdout


def test_ignores_plain_body_without_footer(tmp_path: Path) -> None:
    message = "docs: 补说明\n\n- 这一段是正文，不是 footer\n- 第二行\n"
    assert run_hook(tmp_path, message).returncode == 0


def test_allows_merge_commit(tmp_path: Path) -> None:
    assert run_hook(tmp_path, "Merge branch 'feat/x' into develop\n").returncode == 0
