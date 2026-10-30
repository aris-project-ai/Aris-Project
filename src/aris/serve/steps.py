"""serve 的启动步骤表：每一步的探针（只读）与启动动作。

三类步骤（见 docs/forAiDoc/SERVE.md 第 2 节）：

- ① **import 即就绪**（core / character / behavior）：``start=None``，探针只做自检
- ② **需要外部资源**（data / store.db / store.embed / knowledge）：启动动作由模块自己
  经总线提供（``store.start`` / ``store.embed_preload`` / ``knowledge.start``）；
  ``data`` 只做 ``data/`` 目录分层（可迁移性 D14），没有对应模块
- ③ **入口**（webui）：``blocks=True``，由编排方在打完启动清单后调用（它会阻塞
  到 Ctrl-C）

步骤顺序 = :func:`build_steps` 返回的列表顺序；新增步骤只改本文件。
探针**只读**（不启动任何东西），失败即抛异常——serve 据此打印 `✗` 并按档位处理。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..behavior.runtime import assembly_error, get_runtime, peek_runtime
from ..config import get_settings
from ..core import call, has_service
from .conf import ServeConfig


@dataclass(frozen=True)
class ServeStep:
    """一个启动步骤。"""

    name: str
    label: str
    probe: Callable[[], str]
    level: str = "optional"  # required / optional（required 失败会让依赖它的步骤跳过）
    start: Callable[[], str] | None = None  # None = import 即就绪，无启动动作
    needs: tuple[str, ...] = ()  # 依赖的步骤名（--only 会自动补齐）
    blocks: bool = False  # True = 阻塞步骤（WebUI），编排方最后调用


def _probe_services() -> str:
    """探针：组装后的服务表是否覆盖各模块声明的依赖（缺一即报，不静默）。

    清单由各模块自己声明（如 `webui.REQUIRED_SERVICES`），serve 只负责启动时统一
    核验——原实现散在 `webui.create_app()` 里，只有 WebUI 那条路径会被检查。
    模块开关关闭后，该模块声明的依赖不再核验（它本来就不会装配）。
    """
    from ..modules import module_enabled

    required: tuple[str, ...] = ()
    if module_enabled("webui"):
        from ..webui import REQUIRED_SERVICES

        required = REQUIRED_SERVICES

    missing = [name for name in required if not has_service(name)]
    if missing:
        raise RuntimeError(f"缺少服务：{', '.join(missing)}——检查组装根是否 import 到了所有者模块")
    return f"各模块声明的 {len(required)} 个依赖服务全部就绪"


def _probe_llm() -> str:
    """探针：LLM 配置可读、有可用提供方、体检无错误、审计与 http 服务已注册。"""
    from ..core.llm import load_providers

    config = load_providers(get_settings().llm_providers_file)
    if not config.providers:
        raise RuntimeError("providers.toml 里没有可用提供方，请检查 data/config/providers.toml")
    models = sum(len(p.models) for p in config.providers)
    default = config.default_model or "未设"
    missing = [s for s in ("audit.recent", "audit.summary", "http.request") if not has_service(s)]
    if missing:
        raise RuntimeError(f"缺少服务：{', '.join(missing)}")
    issues = call("llm.providers.check") or []
    errors = [message for level, message in issues if level == "error"]
    if errors:
        raise RuntimeError(f"LLM 配置 {len(errors)} 个错误：{errors[0]}（详情 `aris llm check`）")
    warnings = len(issues) - len(errors)
    tail = f"；{warnings} 个警告" if warnings else ""
    return f"{len(config.providers)} 个提供方 / {models} 个模型，默认 {default}{tail}"


def _probe_character() -> str:
    """探针：角色服务已注册，并报现有角色数（只读，不播种）。"""
    if not has_service("character.system_prompt") or not has_service("character.list"):
        raise RuntimeError("character 服务未注册")
    roles = call("character.list") or []
    names = "、".join(str(role.get("name")) for role in roles) or "无"
    return f"{len(roles)} 个角色（{names}）"


def _start_character() -> str:
    """启动动作：确保至少有一个角色（空目录首次播种默认角色，幂等）。"""
    cid = call("character.resolve")
    roles = call("character.list") or []
    return f"{len(roles)} 个角色，默认 {cid}"


def _probe_behavior() -> str:
    """探针：技能服务已注册 + 进程级运行时是否已装配（v1.0 M1 上收）。

    工具注册表（``tools.execute``）、agent loop（``loop.run``）、``skills.menu``
    原先由会话对象自建，现由一份进程级运行时持有，单例归 `behavior/runtime.py`（v0.4.4 W4）；
    装配失败的原因在这里如实报错，而不是只留一条 assemble 的 warning。
    探针**只读**：用 `peek_runtime()` 看状态，不触发构建。
    """
    if not has_service("skills.list"):
        raise RuntimeError("skills.list 未注册")
    error = assembly_error()
    if error:
        raise RuntimeError(f"behavior 运行时未装配：{error}")

    runtime = peek_runtime()
    if runtime is None:
        return "skills 服务已注册（运行时待 behavior 步骤装配）"
    skills = len(call("skills.list") or [])
    return f"运行时已装配：{runtime.tool_count()} 个工具 / {skills} 个技能"


def _start_behavior() -> str:
    """启动动作：装配进程级 behavior 运行时（幂等；LLM 配置不可用时抛错按档位降级）。"""
    runtime = get_runtime()
    return f"{runtime.tool_count()} 个工具已就绪"


def _probe_data() -> str:
    """探针：``data/`` 分层完整性（可迁移性 D14；只读，缺失只提示）。"""
    from ..datadir import missing_carried

    data_dir = get_settings().data_dir
    missing = missing_carried(data_dir)
    if missing:
        return f"{data_dir}：缺 {'、'.join(missing)}（启动时创建 / 首次运行生成）"
    return f"{data_dir}：必须带的目录齐备"


def _start_data() -> str:
    """启动动作：幂等创建 ``data/`` 下必须带的目录（换机后拷过来就能起）。"""
    from ..datadir import ensure_dirs

    created = ensure_dirs(get_settings().data_dir)
    return f"新建 {', '.join(created)}" if created else "目录已齐备，无新建"


def _probe_db(init_if_missing: bool) -> str:
    """探针：数据库实例是否存在、是否在跑、有多少待执行迁移（不启动）。

    同时报可迁移性三缺口（D14）：二进制能否在本机运行、数据目录属主是否当前用户、
    端口是否被占——这些是"换机后起不来"的三个真实原因，必须在启动前说清楚。
    """
    info: dict[str, Any] = call("store.db_status") or {}
    if not info:
        raise RuntimeError("store.db_status 未注册")
    if not info.get("runnable", True):
        raise RuntimeError(
            f"便携 PostgreSQL 在本机跑不起来：{info.get('runnable_detail')}"
            "——启动时会自动重新获取（需联网）"
        )
    if info.get("ownership_error"):
        raise RuntimeError(str(info["ownership_error"]))
    if not info.get("installed"):
        if init_if_missing:
            return f"未初始化（启动时将自动获取，需联网）@127.0.0.1:{info['port']}"
        raise RuntimeError("便携数据库尚未初始化：执行 `aris db init`")
    if not info.get("running"):
        return f"未运行（启动时将自启）@127.0.0.1:{info['port']}；角色 {info.get('user')}"
    pending = len(info.get("pending_migrations") or [])
    return f"PG 运行中 @127.0.0.1:{info['port']}；角色 {info.get('user')}；待执行迁移 {pending} 条"


def _start_db(autostart: bool, init_if_missing: bool) -> str:
    """启动动作：确保数据库可用（缺则自建）并应用迁移。"""
    info: dict[str, Any] = (
        call("store.start", autostart=autostart, init_if_missing=init_if_missing) or {}
    )
    if not info:
        raise RuntimeError("store.start 未注册")
    if info.get("created"):
        origin = "本次自建并自启"
    elif info.get("started_by_serve"):
        origin = "本次自启"
    elif info.get("running_before"):
        origin = "复用已在运行的实例"
    else:
        origin = "已就绪"
    migrations = len(info.get("migrations") or [])
    return (
        f"PG @127.0.0.1:{info['port']}（{origin}，角色 {info.get('user')}）；"
        f"应用迁移 {migrations} 条"
    )


def _probe_embed() -> str:
    """探针：embedding 配置与预热状态（不触发加载）。"""
    dimension = call("store.embed_dimension")
    state: dict[str, Any] = call("store.embed_status") or {}
    return f"{dimension} 维；{state.get('detail', state.get('status', 'idle'))}"


def _start_embed() -> str:
    """启动动作：后台预热 embedding（立即返回，不等加载完）。"""
    state: dict[str, Any] = call("store.embed_preload") or {}
    if not state:
        raise RuntimeError("store.embed_preload 未注册")
    return f"{state.get('detail', '')}（后台预热，不阻塞启动）"


def _probe_knowledge() -> str:
    """探针：知识库开关与文档/块计数（库不可用时抛错，不静默降级）。

    PG 未运行时不算失败——真实启动时 store.db 会先把它拉起来，故此处只报
    「待数据库启动后建表」，否则 dry-run 会误报一片红。
    """
    info: dict[str, Any] = call("knowledge.status") or {}
    if not info:
        raise RuntimeError("knowledge.status 未注册")
    if not info.get("enabled", True):
        return "已关闭（data/config/knowledge.toml: enabled=false）"
    db: dict[str, Any] = call("store.db_status") or {}
    if not db.get("running"):
        return "待数据库启动后建表（PG 未运行）"
    if info.get("error"):
        raise RuntimeError(str(info["error"]))
    return f"{info.get('docs', 0)} 文档 / {info.get('chunks', 0)} 块"


def _start_knowledge() -> str:
    """启动动作：建表 / 建索引 / 统计（幂等）。"""
    info: dict[str, Any] = call("knowledge.start") or {}
    if not info:
        raise RuntimeError("knowledge.start 未注册")
    if not info.get("enabled", True):
        return "已关闭（data/config/knowledge.toml: enabled=false）"
    return f"{info.get('docs', 0)} 文档 / {info.get('chunks', 0)} 块，索引已就绪"


def _probe_mcp() -> str:
    """探针：mcp server 面状态（只读；连接已在 behavior 装配时发生）。"""
    info: dict[str, Any] = call("mcp.status") or {}
    if not info:
        raise RuntimeError("mcp.status 未注册")
    servers: dict[str, Any] = info.get("servers") or {}
    if not servers:
        return "未配置 server（data/config/mcp.toml 无 [servers.*]）"
    connected = sum(1 for s in servers.values() if s.get("status") == "已连接")
    tools = sum(s.get("tools") or 0 for s in servers.values())
    bad = [
        f"{name}({s.get('status')}" + (f"：{s.get('detail')}" if s.get("detail") else "") + ")"
        for name, s in servers.items()
        if s.get("status") == "已失败"
    ]
    line = f"{len(servers)} 个 server，{connected} 已连接 / {tools} 个工具"
    if bad:
        line += f"；失败 {len(bad)} 个（{'、'.join(bad)}）"
    return line


def _probe_webui() -> str:
    """探针：监听端口是否可用（被占用即抛错，交由档位处理）。"""
    info: dict[str, Any] = call("webui.probe") or {}
    if not info:
        raise RuntimeError("webui.probe 未注册")
    if not info.get("available", False):
        raise RuntimeError(
            f"端口 {info.get('host')}:{info.get('port')} 已被占用"
            "（可能已有 `aris web` / `aris serve` 在运行）"
        )
    mode = "免鉴权：仅本机" if info.get("warning") else "已配密码"
    return f"http://{info['host']}:{info['port']}（{mode}）"


def _start_webui() -> str:
    """启动动作：拉起 WebUI（**阻塞**，直到 Ctrl-C）。"""
    return str(call("webui.start") or "")


def build_steps(config: ServeConfig) -> list[ServeStep]:
    """按配置生成步骤表（列表顺序 = 启动顺序）。"""
    embed_start = _start_embed if config.preload_embedding else None
    return [
        ServeStep("services", "services", _probe_services, level="required"),
        ServeStep("data", "data", _probe_data, start=_start_data),
        ServeStep("core", "core.llm", _probe_llm),
        ServeStep("character", "character", _probe_character, start=_start_character),
        ServeStep("behavior", "behavior", _probe_behavior, start=_start_behavior),
        ServeStep(
            "store.db",
            "store.db",
            lambda: _probe_db(config.init_db),
            level="required",
            start=lambda: _start_db(config.start_db, config.init_db),
        ),
        ServeStep("store.embed", "store.embed", _probe_embed, start=embed_start),
        ServeStep(
            "knowledge",
            "knowledge",
            _probe_knowledge,
            start=_start_knowledge,
            needs=("store.db",),
        ),
        ServeStep("mcp", "mcp", _probe_mcp),
        ServeStep("webui", "webui", _probe_webui, start=_start_webui, blocks=True),
    ]


__all__ = ["ServeStep", "build_steps"]
