"""``data/`` 目录分层（可迁移性 D14，见 docs/developDoc/PORTABILITY-AND-SINGLE-SESSION.md）。

换主机 = 新机 ``git clone`` → 把原机 ``data/`` 全量拷过来 → ``uv run aris serve`` 直接起。
为了让「拷过来就能起」成立，**必须带的目录在启动时幂等创建**（缺什么补什么），
**可重建的东西一律不进 git、丢了自动重获取**。

分层（2026-09-28 定案）：

- **必须带**（丢了就丢记忆 / 人设 / 技能）：``pgdata/``、``knowledge/``、
  ``characters/``、``skills/``、``autorun/``
- **可重建**（丢了自动重获取或重算）：``pg/``、``bin/``、``models/``、``logs/``、各缓存

本模块只做「目录有没有、建没建」，不感知任何业务语义。
"""

from __future__ import annotations

from pathlib import Path

# 启动时幂等创建的目录（相对 data_dir）；其余由各模块首次使用时自建
REQUIRED_DIRS: tuple[str, ...] = ("characters", "skills", "autorun")

# 必须随 data/ 一起搬走的项（缺失只提示，不代为创建）
CARRIED_PATHS: tuple[str, ...] = ("pgdata", "knowledge", "characters", "skills", "autorun")

# 可重建的项（不必带；换机后自动获取 / 重算）
REBUILDABLE_PATHS: tuple[str, ...] = ("pg", "bin", "models", "logs")


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


__all__ = ["CARRIED_PATHS", "REBUILDABLE_PATHS", "REQUIRED_DIRS", "ensure_dirs", "missing_carried"]
