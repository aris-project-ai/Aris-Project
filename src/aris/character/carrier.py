"""角色载体：`data/characters/<cid>/` 目录的读写（v1.0 M2，D1）。

一个角色 = 一个目录：

- `character.toml` —— 可读名 `name` + 四段人设（`intro` / `personality` /
  `tone` / `boundaries`）
- `worldview.md` / `relations.md` / `growth.md` —— 只读占位，填了内容才拼进人设

`cid` 在创建角色时生成（uuid），改名 / 改人设都不影响它：数据库只存 id 绑定
（M2 只管文件，不碰库）。
"""

from __future__ import annotations

import tomllib
import uuid
from dataclasses import dataclass
from pathlib import Path

from .prompt import (
    DEFAULT_BOUNDARIES,
    DEFAULT_INTRO,
    DEFAULT_NAME,
    DEFAULT_PERSONALITY,
    DEFAULT_TONE,
    TEXT_FILES,
    placeholder_text,
)

CHARACTERS_DIR = "characters"
CHARACTER_FILE = "character.toml"
# 人设字段（顺序即播种时写入 toml 的顺序）
_PROFILE_FIELDS = ("name", "intro", "personality", "tone", "boundaries")


def _meaningful(text: str) -> bool:
    """是否有实质内容（只有空行 / HTML 注释的占位文件视为空）。"""
    return any(line.strip() and not line.strip().startswith("<!--") for line in text.splitlines())


@dataclass(frozen=True)
class CharacterInfo:
    """列表项：cid + 可读名 + 目录。"""

    cid: str
    name: str
    path: Path


@dataclass(frozen=True)
class CharacterProfile:
    """一个角色的完整人设（toml 四段 + 三段只读文本）。"""

    cid: str
    name: str
    intro: str
    personality: str
    tone: str
    boundaries: str
    worldview: str = ""
    relations: str = ""
    growth: str = ""

    def system_prompt(self) -> str:
        """拼出该角色的系统提示词（三段文本有内容时追加成小节）。"""
        parts = [
            self.intro.strip(),
            f"你的性格：{self.personality.strip()}",
            f"你的语气：{self.tone.strip()}",
            self.boundaries.strip(),
        ]
        for title, text in (
            ("世界观", self.worldview),
            ("人际关系", self.relations),
            ("成长轨迹", self.growth),
        ):
            if _meaningful(text):
                parts.append(f"# {title}\n{text.strip()}")
        return "\n".join(part for part in parts if part)


def _toml_str(value: str) -> str:
    """把文本写成 TOML 字符串（单行为普通串，含换行用多行基本串）。"""
    if "\n" not in value and '"' not in value and "\\" not in value:
        return f'"{value}"'
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"""\n{escaped}\n"""'


def _render_toml(values: dict[str, str]) -> str:
    """按固定字段顺序生成 character.toml 文本。"""
    lines = ["# 角色载体（v1.0 M2）：改名 / 改人设不影响 cid", ""]
    lines.extend(f"{key} = {_toml_str(values.get(key, ''))}" for key in _PROFILE_FIELDS)
    return "\n".join(lines) + "\n"


class CharacterStore:
    """`data/characters/` 目录的读写门面。"""

    def __init__(self, root: Path) -> None:
        self.root = root

    def cids(self) -> list[str]:
        """现有角色 cid（按目录名排序，稳定可复现）。"""
        if not self.root.is_dir():
            return []
        return sorted(
            path.name for path in self.root.iterdir() if (path / CHARACTER_FILE).is_file()
        )

    def list(self) -> list[CharacterInfo]:
        """列出角色；坏目录（toml 损坏）不阻塞列表，名字退化成 cid。"""
        infos: list[CharacterInfo] = []
        for cid in self.cids():
            try:
                name = self.load(cid).name
            except (OSError, ValueError, KeyError):
                name = cid
            infos.append(CharacterInfo(cid=cid, name=name, path=self.root / cid))
        return infos

    def exists(self, cid: str) -> bool:
        return (self.root / cid / CHARACTER_FILE).is_file()

    def load(self, cid: str) -> CharacterProfile:
        """读一个角色；不存在时抛错并列出可用 cid（防静默串号）。"""
        config = self.root / cid / CHARACTER_FILE
        if not config.is_file():
            raise FileNotFoundError(self._missing(cid))
        with config.open("rb") as handle:
            data = tomllib.load(handle)
        texts: dict[str, str] = {}
        for filename in TEXT_FILES:
            path = self.root / cid / filename
            texts[filename.removesuffix(".md")] = path.read_text("utf-8") if path.is_file() else ""
        return CharacterProfile(
            cid=cid,
            name=str(data.get("name") or cid),
            intro=str(data.get("intro") or ""),
            personality=str(data.get("personality") or ""),
            tone=str(data.get("tone") or ""),
            boundaries=str(data.get("boundaries") or ""),
            **texts,
        )

    def system_prompt(self, cid: str) -> str:
        return self.load(cid).system_prompt()

    def create(
        self,
        *,
        name: str = DEFAULT_NAME,
        cid: str | None = None,
        fields: dict[str, str] | None = None,
    ) -> CharacterProfile:
        """新建角色目录（cid 缺省时按 uuid 生成），返回读回的角色。"""
        cid = cid or uuid.uuid4().hex[:12]
        directory = self.root / cid
        if directory.exists():
            raise FileExistsError(f"角色目录已存在：{directory}")
        directory.mkdir(parents=True)
        values = {
            "name": name,
            "intro": DEFAULT_INTRO,
            "personality": DEFAULT_PERSONALITY,
            "tone": DEFAULT_TONE,
            "boundaries": DEFAULT_BOUNDARIES,
        }
        values.update(fields or {})
        (directory / CHARACTER_FILE).write_text(_render_toml(values), "utf-8")
        for filename in TEXT_FILES:
            (directory / filename).write_text(placeholder_text(filename), "utf-8")
        return self.load(cid)

    def seed_default(self) -> str:
        """空目录首次播种默认角色并返回其 cid（幂等：已有角色就返回最早的一个）。"""
        existing = self.cids()
        if existing:
            return existing[0]
        return self.create().cid

    def resolve(self, cid: str | None = None) -> str:
        """选定 cid：显式给的校验存在，否则播种 / 取默认角色。"""
        if cid:
            if not self.exists(cid):
                raise FileNotFoundError(self._missing(cid))
            return cid
        return self.seed_default()

    def _missing(self, cid: str) -> str:
        known = "、".join(self.cids()) or "无"
        return f"角色不存在：{cid}（现有：{known}）"


def characters_root(data_dir: Path | None = None) -> Path:
    """角色根目录 `<data_dir>/characters/`。"""
    if data_dir is None:
        from ..infra.settings import get_settings

        data_dir = get_settings().data_dir
    return Path(data_dir) / CHARACTERS_DIR


_store: CharacterStore | None = None


def get_store() -> CharacterStore:
    """进程级角色仓库（默认指向 `settings.data_dir/characters`）。"""
    global _store
    if _store is None:
        _store = CharacterStore(characters_root())
    return _store


def reset_store() -> None:
    """丢掉缓存的门面（换 data_dir / 测试用）。"""
    global _store
    _store = None
