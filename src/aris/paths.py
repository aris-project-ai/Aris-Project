"""统一数据目录解析。

优先级：
- ARIS_DATA_DIR（进程环境）> 开发树 ./data > 安装 ~/.project-aris
"""

from __future__ import annotations

import os
from pathlib import Path


def _is_dev_tree(root: Path) -> bool:
    try:
        return (root / "pyproject.toml").exists() and (root / "src" / "aris").exists()
    except (OSError, RuntimeError):
        return False


def _find_dev_root_via_cwd() -> Path | None:
    try:
        cwd = Path.cwd().resolve()
        if _is_dev_tree(cwd):
            return cwd
    except (OSError, RuntimeError):
        pass
    return None


def _find_dev_root_via_file() -> Path | None:
    try:
        here = Path(__file__).resolve()
        for cand in [here.parent.parent.parent, here.parent.parent, here.parent]:
            if _is_dev_tree(cand):
                return cand
    except (OSError, RuntimeError):
        pass
    return None


def data_root() -> Path:
    env = os.environ.get("ARIS_DATA_DIR", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        return p

    cwd_dev = _find_dev_root_via_cwd()
    if cwd_dev is not None:
        return (cwd_dev / "data").resolve()

    file_dev = _find_dev_root_via_file()
    if file_dev is not None:
        try:
            cwd = Path.cwd().resolve()
            # 只有在当前工作目录位于该开发树内时才认为是开发模式
            cwd.relative_to(file_dev)
            return (file_dev / "data").resolve()
        except (OSError, RuntimeError, ValueError):
            pass

    p = Path.home() / ".project-aris"
    return p.expanduser().resolve()


def config_dir() -> Path:
    return data_root() / "config"


def state_dir() -> Path:
    return data_root() / "state"


def logs_dir() -> Path:
    return data_root() / "logs"


def env_file() -> Path:
    return data_root() / "settings.toml"


def characters_dir() -> Path:
    return data_root() / "characters"


def skills_dir() -> Path:
    return data_root() / "skills"


def models_dir() -> Path:
    return data_root() / "models"


def notes_dir() -> Path:
    return data_root() / "notes"
