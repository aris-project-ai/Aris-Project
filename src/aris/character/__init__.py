"""character 模块 —— 人格系统 / 角色载体（v1.0 M2）。

人设不再是模块常量：每个角色一个目录 `data/characters/<cid>/`，本模块是
「加载器 + 注册表」，经跨模块通讯总线（CMCB）对外提供三个服务：

- `character.system_prompt(cid)` —— 该角色的系统提示词；**`cid` 必填无默认**
  （防静默串号），显式给了不存在的 cid 直接抛错
- `character.list()` —— 角色列表（cid / 可读名 / 目录）
- `character.resolve(cid=None)` —— 选定 cid：显式给的校验存在，否则空目录时
  首次**播种**默认角色（幂等），已有角色时返回默认那个

后续演进：世界观 / 人际关系 / 成长轨迹（占位文件已建，填内容即拼进人设）。
"""

from ..core import provide
from .carrier import (
    CHARACTER_FILE,
    CHARACTERS_DIR,
    CharacterInfo,
    CharacterProfile,
    CharacterStore,
    characters_root,
    get_store,
    reset_store,
)
from .prompt import DEFAULT_NAME, TEXT_FILES


def _system_prompt(cid: str) -> str:
    """返回指定角色的系统提示词（cid 必填：防静默串号）。"""
    return get_store().system_prompt(cid)


def _list() -> list[dict[str, str]]:
    """角色列表（cid / 可读名 / 目录）。"""
    return [
        {"cid": info.cid, "name": info.name, "path": str(info.path)} for info in get_store().list()
    ]


def _resolve(cid: str | None = None) -> str:
    """选定角色 cid（显式给的校验存在；否则播种 / 取默认角色）。"""
    return get_store().resolve(cid)


# 注册为统一服务：任何模块经 call("character.*") 取角色信息
provide("character.system_prompt", _system_prompt)
provide("character.list", _list)
provide("character.resolve", _resolve)

__all__ = [
    "CHARACTERS_DIR",
    "CHARACTER_FILE",
    "DEFAULT_NAME",
    "TEXT_FILES",
    "CharacterInfo",
    "CharacterProfile",
    "CharacterStore",
    "characters_root",
    "get_store",
    "reset_store",
]
