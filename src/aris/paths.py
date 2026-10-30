"""统一数据目录解析（唯一来源）。

优先级：ARIS_DATA_DIR（进程环境）> 开发树 ./data > 安装 ~/.project-aris。

开发树判定：仓库根同时存在 pyproject.toml 与 src/aris。打包后的入口
（paris / paris-gui）会显式注入 ARIS_DATA_DIR，不依赖这个猜测。

本模块只回答「东西放哪」，不做业务；配置内容见 aris.config 与 aris.cfgtoml。
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
        return Path(env).expanduser().resolve()

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

    return (Path.home() / ".project-aris").expanduser().resolve()


def config_dir() -> Path:
    return data_root() / "config"


def state_dir() -> Path:
    return data_root() / "state"


def logs_dir() -> Path:
    return data_root() / "logs"


def settings_file() -> Path:
    return config_dir() / "settings.toml"


def secrets_file() -> Path:
    return config_dir() / "secrets.toml"


def characters_dir() -> Path:
    return data_root() / "characters"


def skills_dir() -> Path:
    return data_root() / "skills"


def models_dir() -> Path:
    return data_root() / "models"


def notes_dir() -> Path:
    return data_root() / "notes"


# 随包种子模板：用户配置缺失时作为默认值来源，也用于首次启动播种
SEED_CONFIG_DIR = Path(__file__).resolve().parent / "seed" / "config"


def seed_config_file(name: str) -> Path | None:
    """返回某个配置的种子模板路径（没有该模板时返回 None）。"""
    p = SEED_CONFIG_DIR / name
    return p if p.is_file() else None


def seed_config() -> list[str]:
    """把种子模板幂等播种到 data/config/。

    只补缺失的文件，绝不覆盖用户改动；secrets.toml 新建后置 0600。
    返回本次真正新建的文件名列表（供启动清单打印）。
    """
    from loguru import logger

    created: list[str] = []
    if not SEED_CONFIG_DIR.is_dir():
        return created

    cfg = config_dir()
    try:
        cfg.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning(f"配置目录创建失败（{cfg}）：{exc}；改用随包模板的默认值")
        return created

    for template in sorted(SEED_CONFIG_DIR.glob("*.toml")):
        target = cfg / template.name
        if target.exists():
            continue
        try:
            target.write_bytes(template.read_bytes())
        except OSError as exc:
            logger.warning(f"播种配置失败（{template.name}）：{exc}")
            continue
        if template.name == "secrets.toml":
            try:
                target.chmod(0o600)
            except OSError as exc:
                logger.warning(f"secrets.toml 权限设置失败：{exc}")
        created.append(template.name)
    return created


# ---------- data/ 分层（可迁移性 D14） ----------
#
# 换机 = 新机 git clone → 把原机 data/ 全量拷过来 → uv run aris serve 直接起。
# 为了让「拷过来就能起」成立：必须带的目录启动时幂等创建；可重建的东西丢了自动重获取。

# 启动时幂等创建的目录（相对 data_dir）；其余由各模块首次使用时自建
REQUIRED_DIRS: tuple[str, ...] = ("characters", "skills", "autorun")

# 必须随 data/ 一起搬走的项（缺失只提示，不代为创建）
CARRIED_PATHS: tuple[str, ...] = (
    "pgdata",
    "knowledge",
    "characters",
    "skills",
    "autorun",
    "config",
)

# 可重建的项（不必带；换机后自动获取 / 重算）
REBUILDABLE_PATHS: tuple[str, ...] = ("pg", "bin", "models", "logs", "state")


def ensure_dirs(data_dir: Path | str) -> list[str]:
    """幂等创建必须的目录，返回**本次真正新建**的相对路径（供日志）。"""
    created: list[str] = []
    for rel in REQUIRED_DIRS:
        target = Path(data_dir) / rel
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(rel)
    return created


def missing_carried(data_dir: Path | str) -> list[str]:
    """列出「必须带但当前不存在」的项（空列表 = 分层完整）。

    ``pgdata`` / ``knowledge`` 首次运行时本来就不存在，故调用方（serve 探针 /
    ``aris doctor``）应把结果当作**提示**而不是错误。
    """
    root = Path(data_dir)
    return [rel for rel in CARRIED_PATHS if not (root / rel).exists()]
