"""版本号脚本的回归测试（shell 层）。

覆盖：历史 tag 兼容、beta/正式同号查重、递增校验、bump/release-check 的拒绝与通过路径。
这些测试不碰真实仓库，全部在 tmp_path 里新建 git 仓库。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def run(
    cmd: list[str],
    cwd: Path,
    *,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """执行子进程；默认失败即抛，便于准备仓库。"""
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
        env=env,
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], repo)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """一个带初始提交的临时 git 仓库。"""
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "test")
    git(path, "config", "commit.gpgsign", "false")
    git(path, "commit", "--allow-empty", "-qm", "init")
    return path


def lib_call(repo: Path, code: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """在临时仓库里 source lib-version.sh 后执行一段 shell。"""
    script = f'. "{SCRIPTS / "lib-version.sh"}"\n{code}'
    return run(["bash", "-c", script], repo, check=check)


def fake_uv(tmp_path: Path, version: str = "0.5.0") -> dict[str, str]:
    """伪造 uv：bump 脚本里的 lock/sync/run 都直接成功。"""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    uv = bindir / "uv"
    uv.write_text(f'#!/bin/sh\nif [ "$1" = "run" ]; then\n    echo "Aris {version}"\nfi\nexit 0\n')
    uv.chmod(0o755)
    return {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}


def make_bump_repo(repo: Path, version: str = "0.4.2") -> Path:
    """把 bump 需要的脚本与版本文件放进临时仓库，并切到 develop。"""
    (repo / "scripts").mkdir(exist_ok=True)
    for name in ("lib-version.sh", "bump-version.sh"):
        shutil.copy(SCRIPTS / name, repo / "scripts" / name)
    (repo / "src" / "aris").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "aris" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    git(repo, "checkout", "-q", "-B", "develop")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "setup")
    return repo


def make_release_repo(repo: Path, version: str = "0.5.0") -> Path:
    """把 release-check 需要的脚本、pyproject 与版本文件放进临时仓库。"""
    (repo / "scripts").mkdir(exist_ok=True)
    for name in ("lib-version.sh", "release-check.sh"):
        shutil.copy(SCRIPTS / name, repo / "scripts" / name)
    (repo / "src" / "aris").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "aris" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "aris"\ndynamic = ["version"]\n\n'
        '[tool.setuptools.dynamic]\nversion = {attr = "aris.__version__"}\n\n'
        '[tool.uv]\ncache-keys = [{ file = "src/aris/__init__.py" }]\n'
    )
    (repo / "changelogs").mkdir()
    (repo / "changelogs" / f"{version}.md").write_text(
        f"# {version}\n\n## 新增\n- 测试用变更记录\n", encoding="utf-8"
    )
    git(repo, "checkout", "-q", "-B", "develop")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "setup")
    return repo


def bump(
    repo: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return run(["bash", "scripts/bump-version.sh", *args], repo, check=False, env=env)


def release_check(repo: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return run(["bash", "scripts/release-check.sh"], repo, check=False, env=env)


# ---- lib-version.sh ----


def test_legacy_beta_tag_is_detected(repo: Path) -> None:
    git(repo, "tag", "v0.4.2-beta")
    out = lib_call(repo, "version_existing_tag 0.4.2")
    assert out.stdout.strip() == "v0.4.2-beta"


def test_beta_and_release_share_the_same_number(repo: Path) -> None:
    git(repo, "tag", "beta-v1.0.1")
    out = lib_call(repo, "version_existing_tag 1.0.1")
    assert out.stdout.strip() == "beta-v1.0.1"


def test_free_number_is_not_reported(repo: Path) -> None:
    out = lib_call(repo, "version_existing_tag 2.0.0", check=False)
    assert out.returncode == 1
    assert out.stdout.strip() == ""


@pytest.mark.parametrize(
    ("left", "right", "returncode"),
    [
        ("1.0.0", "0.9.9", 0),
        ("0.10.0", "0.9.0", 0),
        ("1.0.1.2", "1.0.1", 0),
        ("1.0.0", "1.0.0", 1),
        ("1.0.0", "1.0.1", 1),
    ],
)
def test_version_gt(repo: Path, left: str, right: str, returncode: int) -> None:
    out = lib_call(repo, f"version_gt {left} {right}", check=False)
    assert out.returncode == returncode


def test_last_number_handles_legacy_suffix(repo: Path) -> None:
    for tag in ("v0.4.1", "v0.4.2-beta", "beta-v0.5.0", "v0.10.0"):
        git(repo, "tag", tag)
    out = lib_call(repo, "version_last_number")
    assert out.stdout.strip() == "0.10.0"


# ---- bump-version.sh ----


def test_bump_rejects_used_number(repo: Path) -> None:
    make_bump_repo(repo)
    git(repo, "tag", "beta-v0.5.0")
    out = bump(repo, "0.5.0")
    assert out.returncode == 1
    assert "已被 tag beta-v0.5.0 占用" in out.stderr


def test_bump_rejects_lower_number(repo: Path) -> None:
    make_bump_repo(repo)
    git(repo, "tag", "v0.4.2-beta")
    out = bump(repo, "0.4.1")
    assert out.returncode == 1
    assert "必须大于" in out.stderr


def test_bump_rejects_dev_suffix(repo: Path) -> None:
    make_bump_repo(repo)
    out = bump(repo, "0.5.0.dev0")
    assert out.returncode == 2
    assert "不带 .dev0" in out.stderr


def test_bump_rejects_same_version(repo: Path) -> None:
    make_bump_repo(repo)
    out = bump(repo, "0.4.2")
    assert out.returncode == 2
    assert "相同" in out.stderr


def test_bump_writes_plain_number(repo: Path, tmp_path: Path) -> None:
    make_bump_repo(repo)
    out = bump(repo, "0.5.0", env=fake_uv(tmp_path))
    assert out.returncode == 0, out.stderr
    content = (repo / "src" / "aris" / "__init__.py").read_text()
    assert '__version__ = "0.5.0"' in content
    assert ".dev0" not in content


@pytest.mark.parametrize(
    ("arg", "expected"),
    [("patch", "0.4.3"), ("minor", "0.5.0"), ("major", "1.0.0")],
)
def test_bump_increments(repo: Path, tmp_path: Path, arg: str, expected: str) -> None:
    make_bump_repo(repo)
    out = bump(repo, arg, env=fake_uv(tmp_path, expected))
    assert out.returncode == 0, out.stderr
    content = (repo / "src" / "aris" / "__init__.py").read_text()
    assert f'__version__ = "{expected}"' in content


def test_bump_rejects_below_current_even_without_tags(repo: Path) -> None:
    make_bump_repo(repo, version="0.5.0")
    out = bump(repo, "0.4.9")
    assert out.returncode == 1
    assert "必须大于" in out.stderr


# ---- release-check.sh ----


def test_release_check_rejects_used_number(repo: Path, tmp_path: Path) -> None:
    make_release_repo(repo)
    git(repo, "tag", "beta-v0.5.0")
    out = release_check(repo, fake_uv(tmp_path))
    assert out.returncode == 1
    assert "已被 tag beta-v0.5.0 占用" in out.stdout


def test_release_check_rejects_non_increasing_number(repo: Path, tmp_path: Path) -> None:
    make_release_repo(repo, version="0.5.0")
    git(repo, "tag", "v0.6.0")
    out = release_check(repo, fake_uv(tmp_path))
    assert out.returncode == 1
    assert "必须大于" in out.stdout


def test_release_check_rejects_dev_suffix(repo: Path, tmp_path: Path) -> None:
    make_release_repo(repo, version="0.5.0.dev0")
    out = release_check(repo, fake_uv(tmp_path))
    assert out.returncode == 1
    assert "不再使用 .devN" in out.stdout


def test_release_check_passes_with_free_number(repo: Path, tmp_path: Path) -> None:
    make_release_repo(repo)
    out = release_check(repo, fake_uv(tmp_path))
    assert out.returncode == 0, out.stdout


def test_release_check_requires_changelog(repo: Path, tmp_path: Path) -> None:
    make_release_repo(repo)
    (repo / "changelogs" / "0.5.0.md").unlink()
    out = release_check(repo, fake_uv(tmp_path))
    assert out.returncode == 1
    assert "缺少 changelogs/0.5.0.md" in out.stdout


# ---- alpha 渠道（v0.4.4 W6）----


def test_alpha_tag_occupies_number(repo: Path) -> None:
    git(repo, "tag", "alpha-v1.0.0")
    out = lib_call(repo, "version_existing_tag 1.0.0")
    assert out.stdout.strip() == "alpha-v1.0.0"


def test_alpha_tag_counts_as_last_number(repo: Path) -> None:
    for tag in ("v0.4.1", "alpha-v0.9.0", "beta-v0.8.0"):
        git(repo, "tag", tag)
    out = lib_call(repo, "version_last_number")
    assert out.stdout.strip() == "0.9.0"


def test_bump_rejects_number_used_by_alpha(repo: Path) -> None:
    make_bump_repo(repo)
    git(repo, "tag", "alpha-v0.5.0")
    out = bump(repo, "0.5.0")
    assert out.returncode == 1
    assert "已被 tag alpha-v0.5.0 占用" in out.stderr


def test_bump_prints_alpha_tag_hint(repo: Path, tmp_path: Path) -> None:
    make_bump_repo(repo)
    out = bump(repo, "0.5.0", env=fake_uv(tmp_path))
    assert out.returncode == 0, out.stderr
    assert "alpha-v0.5.0" in out.stdout


def test_release_check_rejects_number_used_by_alpha(repo: Path, tmp_path: Path) -> None:
    make_release_repo(repo)
    git(repo, "tag", "alpha-v0.5.0")
    out = release_check(repo, fake_uv(tmp_path))
    assert out.returncode == 1
    assert "已被 tag alpha-v0.5.0 占用" in out.stdout
