"""模块开关（data/config/modules.toml）：7 个业务模块的启停与依赖解析。

规则（v0.4.4 W3；决策 D7 / D8）：
- 关闭模块 = `serve.assemble()` **不 import** 它（模块服务在 import 时自注册，必须
  先读配置再决定 import）；
- 用户主动关闭的模块被依赖时：记 error 日志、跳过依赖方、**不退出程序**；
- `enable / disable` 只写 modules.toml 的布尔值，不碰运行中的进程，下一次启动生效；
- 仍为 required 的只有「启用 store 时的 store.db」。

本模块是纯元数据 + 配置读写，**不 import serve，也不 import 任何业务模块**，
CLI 与 serve 共用。
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from loguru import logger

from . import paths

MODULES_FILE = "modules.toml"


@dataclass(frozen=True)
class ModuleSpec:
    """一个可开关模块的静态描述。"""

    name: str
    label: str
    import_path: str | None = None  # 组装根 import 的包路径；None = 暂无代码
    depends_on: tuple[str, ...] = ()
    services: tuple[str, ...] = ()  # 服务名前缀（探针/文档用）
    steps: tuple[str, ...] = ()  # serve 步骤名


# 顺序 = 组装根的 import 顺序（依赖在前）
MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        "store",
        "存储（便携 PG + embedding）",
        "aris.store",
        services=("store.",),
        steps=("store.db", "store.embed"),
    ),
    ModuleSpec(
        "knowledge",
        "知识库（RAG 摄入 / 检索）",
        "aris.knowledge",
        depends_on=("store",),
        services=("knowledge.",),
        steps=("knowledge",),
    ),
    ModuleSpec(
        "mcp",
        "通用 MCP 客户端",
        "aris.mcp",
        services=("mcp.",),
        steps=("mcp",),
    ),
    ModuleSpec(
        "behavior",
        "行为（工具 / 技能 / agent loop）",
        "aris.behavior",
        services=("tools.", "loop.", "skills."),
        steps=("behavior",),
    ),
    ModuleSpec(
        "webui",
        "管理后台",
        "aris.webui",
        depends_on=("store", "knowledge"),
        services=("webui.",),
        steps=("webui",),
    ),
    ModuleSpec(
        "character",
        "角色载体",
        "aris.character",
        services=("character.",),
        steps=("character",),
    ),
    ModuleSpec(
        "voice",
        "语音（STT / TTS，占位）",
        "aris.voice",
        services=("voice.",),
    ),
)

_BY_NAME = {spec.name: spec for spec in MODULES}


@dataclass
class ModulesConfig:
    """modules.toml 的 `[modules]` 表（缺键 = true）。"""

    store: bool = True
    knowledge: bool = True
    mcp: bool = True
    behavior: bool = True
    webui: bool = True
    character: bool = True
    voice: bool = True


@dataclass(frozen=True)
class ModulesState:
    """解析后的模块状态：实际是否装配 + 被关闭的原因。"""

    enabled: dict[str, bool]
    reasons: dict[str, str]

    def enabled_steps(self) -> dict[str, str]:
        """被关闭模块对应的 serve 步骤 → 跳过原因（供启动清单显示）。"""
        skip: dict[str, str] = {}
        for spec in MODULES:
            if self.enabled.get(spec.name, True):
                continue
            reason = self.reasons.get(spec.name, "")
            for step in spec.steps:
                skip[step] = f"模块 {spec.name} 已关闭" + (f"（{reason}）" if reason else "")
        return skip

    def import_paths(self) -> list[tuple[str, str]]:
        """本次应 import 的 (模块名, 包路径)，按依赖顺序。"""
        return [
            (spec.name, spec.import_path)
            for spec in MODULES
            if spec.import_path and self.enabled.get(spec.name, False)
        ]


def modules_file() -> Path:
    """用户 modules.toml 的路径（缺失时由 paths.seed_config() 播种）。"""
    return paths.config_dir() / MODULES_FILE


def load_modules(path: Path | None = None) -> ModulesConfig:
    """读 `[modules]` 表；文件缺失/写坏/类型不对都按 true 兜底并记 warning。"""
    p = path or modules_file()
    cfg = ModulesConfig()
    if not p.is_file():
        return cfg
    try:
        data = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.warning(f"模块开关读取失败（{p}）：{exc}；按全部启用处理")
        return cfg
    table = data.get("modules")
    if table is None:
        logger.warning(f"{p} 缺少 [modules] 表；按全部启用处理")
        return cfg
    if not isinstance(table, dict):
        logger.warning(f"{p} 的 [modules] 不是表；按全部启用处理")
        return cfg

    known = {spec.name for spec in MODULES}
    for name in sorted(set(table) - known):
        logger.warning(f"未知模块开关 {name!r}（{p}），已忽略")
    for field in fields(cfg):
        value = table.get(field.name)
        if value is None:
            continue
        if not isinstance(value, bool):
            logger.warning(f"模块开关 {field.name} 不是布尔值（{p}），已忽略")
            continue
        setattr(cfg, field.name, value)
    return cfg


def resolve_modules(
    cfg: ModulesConfig | None = None,
    *,
    overrides: dict[str, bool] | None = None,
) -> ModulesState:
    """按依赖关系解析实际启停：依赖被关的模块级联关闭（记原因）。"""
    cfg = cfg or load_modules()
    raw = {spec.name: getattr(cfg, spec.name, True) for spec in MODULES}
    if overrides:
        raw.update(overrides)

    enabled: dict[str, bool] = {}
    reasons: dict[str, str] = {}
    for spec in MODULES:
        if not raw[spec.name]:
            enabled[spec.name] = False
            reasons[spec.name] = f"用户在 {MODULES_FILE} 关闭"
            continue
        off = [dep for dep in spec.depends_on if not enabled.get(dep, False)]
        if off:
            enabled[spec.name] = False
            reasons[spec.name] = f"依赖的模块已关闭：{', '.join(off)}"
            continue
        enabled[spec.name] = True
    return ModulesState(enabled=enabled, reasons=reasons)


def module_enabled(name: str, path: Path | None = None) -> bool:
    """某模块实际是否会装配（含依赖级联）；未知模块名返回 False。"""
    if name not in _BY_NAME:
        return False
    return resolve_modules(load_modules(path)).enabled.get(name, False)


def switch_warning(name: str, enabled: bool) -> str | None:
    """预演一次切换：返回会级联关闭的其他模块提示（不写文件）。"""
    if name not in _BY_NAME:
        return None
    cfg = load_modules()
    state = resolve_modules(cfg, overrides={name: enabled})
    if enabled and not state.enabled.get(name):
        reason = state.reasons.get(name, "依赖不满足")
        return f"{name} 仍会被跳过：{reason}（先启用依赖的模块）"
    affected = [
        other.name
        for other in MODULES
        if other.name != name and not state.enabled.get(other.name, True)
    ]
    if affected:
        return f"这会级联关闭：{', '.join(affected)}"
    return None


def set_module_enabled(name: str, enabled: bool, path: Path | None = None) -> Path:
    """改写 modules.toml 里某模块的布尔值（保留其余注释与键），返回文件路径。"""
    if name not in _BY_NAME:
        raise ValueError(f"未知模块 {name!r}；可选：{', '.join(_BY_NAME)}")
    p = path or modules_file()
    if not p.is_file():
        p.parent.mkdir(parents=True, exist_ok=True)
        seed = paths.seed_config_file(MODULES_FILE)
        p.write_text(
            seed.read_text(encoding="utf-8") if seed is not None else "[modules]\n",
            encoding="utf-8",
        )

    lines = p.read_text(encoding="utf-8").splitlines()
    value = "true" if enabled else "false"
    pattern = re.compile(rf"^(\s*{re.escape(name)}\s*=\s*)(?:true|false)(\s*(?:#.*)?)$")
    in_modules = False
    replaced = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            in_modules = stripped == "[modules]"
            continue
        if in_modules and pattern.match(line):
            lines[i] = pattern.sub(rf"\g<1>{value}\g<2>", line, count=1)
            replaced = True
            break

    if not replaced:
        if not any(line.strip() == "[modules]" for line in lines):
            if lines and lines[-1].strip():
                lines.append("")
            lines.append("[modules]")
        idx = next(i for i, line in enumerate(lines) if line.strip() == "[modules]")
        lines.insert(idx + 1, f"{name} = {value}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


__all__ = [
    "MODULES",
    "MODULES_FILE",
    "ModuleSpec",
    "ModulesConfig",
    "ModulesState",
    "load_modules",
    "module_enabled",
    "modules_file",
    "resolve_modules",
    "set_module_enabled",
    "switch_warning",
]
