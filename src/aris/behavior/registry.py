"""工具注册表：统一登记工具的执行函数与 schema。

来源分三类（AGENTS.md §6 CMCB）：
- behavior 自家内置工具：`tools.register_builtin_tools` 直接登记；
- 技能工具：SkillManager 激活时登记；
- 业务模块声明的 agent 工具：模块经 `<模块名>.ai_tools` 总线服务给出
  `ToolSpec` 清单，`register_declared_tools` 在装配时探询收编——工具的 fn
  本身不上总线，总线只传声明（契约见 `core/tools.py`）；
- **动态工具**（如 mcp 模块供的远端 MCP 工具，列表会变）：经总线服务
  `tools.sync_generation` 做**世代同步**——旧代（同 owner）全量卸下 ↔ 新代
  全量登记，新代校验失败保旧代（dsh 验证过的两相式，避免工具面空窗）。

执行失败宽容降级：返回错误文本给模型消化，不抛到 UI（设计哲学第 3 条）。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from loguru import logger

from aris.core.bus import call, provide, services
from aris.core.llm.message import ToolDefinition
from aris.core.tools import ToolFn, ToolSpec

# 声明契约后缀：模块 provide("<模块名>.ai_tools", fn)，fn 返回 list[ToolSpec]
DECLARATION_SUFFIX = ".ai_tools"


@dataclass
class RegisteredTool:
    """注册表里的一项：定义（给 LLM 看）+ 执行函数。

    needs_context：工具是否需要对话上下文（由 agent loop 拼好文本注入
        `_context` 关键字，如 http_request 的 URL 来源校验）。
    owner：提供方模块名（"" = behavior 内置），供 WebUI 工具页展示与开关。
    enabled：模型可见性（False 时 `definitions()` 过滤，不进请求工具面；
        执行侧 fn 的降级文案仍在，手动调用可读取），来源见 ToolSpec。
    """

    definition: ToolDefinition
    fn: ToolFn
    needs_context: bool = False
    owner: str = ""
    enabled: bool = True


class ToolRegistry:
    """工具注册表：name → RegisteredTool。"""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        # 登记表锁：mcp 的世代同步发生在 **mcp owner 线程**，agent loop 在主线程
        # 读 —— 同一把 RLock 保证整表/单条互不撕裂（RLock 允许嵌套 register）。
        self._lock = threading.RLock()
        # 声明探询失败的提供方清单：[(provider 服务名, 错误摘要)]。
        # 每轮 `register_declared_tools` 重置；WebUI 工具页据此醒目展示
        # 「声明了但没收编上」的条目（日志是时间线，这里是状态面）。
        self.declaration_failures: list[tuple[str, str]] = []
        # 注册为统一服务：工具执行统一走 core.call("tools.execute", ...)
        provide("tools.execute", self.execute)
        # 世代同步：动态工具提供方（mcp）经它做「旧代↔新代」两相式换装
        provide("tools.sync_generation", self.sync_generation)

    def register(
        self,
        name: str,
        *,
        description: str,
        parameters: dict,
        fn: ToolFn,
        needs_context: bool = False,
        owner: str = "",
        enabled: bool = True,
    ) -> None:
        """登记一个工具（持锁）。重名时记 warning 后覆盖（后注册优先）。"""
        with self._lock:
            if name in self._tools:
                logger.warning(
                    f"工具 {name} 重名注册（{owner or 'behavior 内置'} 覆盖 "
                    f"{self._tools[name].owner or 'behavior 内置'} 的旧定义）"
                )
            self._tools[name] = RegisteredTool(
                definition=ToolDefinition(
                    name=name, description=description, parameters=parameters
                ),
                fn=fn,
                needs_context=needs_context,
                owner=owner,
                enabled=enabled,
            )

    def register_spec(self, spec: ToolSpec) -> None:
        """收编一条业务模块的工具声明；非法声明抛 ValueError（探询层负责降级）。"""
        if not isinstance(spec.name, str) or not spec.name.strip():
            raise ValueError("工具声明缺少合法 name")
        if not callable(spec.fn):
            raise ValueError(f"工具 {spec.name} 的 fn 不可调用")
        if not isinstance(spec.parameters, dict):
            raise ValueError(f"工具 {spec.name} 的 parameters 不是对象")
        self.register(
            spec.name,
            description=spec.description,
            parameters=spec.parameters,
            fn=spec.fn,
            needs_context=spec.needs_context,
            owner=spec.owner,
            enabled=spec.enabled,
        )

    def items(self) -> list[RegisteredTool]:
        """全部登记项（按注册顺序，含 disabled），供 CLI / WebUI 工具页枚举。"""
        with self._lock:
            return list(self._tools.values())

    def definitions(self) -> list[ToolDefinition]:
        """返回**模型可见**的工具定义（按注册顺序），供请求携带。

        disabled 的工具不进请求工具面（`ToolSpec.enabled` 契约）。
        """
        with self._lock:
            return [t.definition for t in self._tools.values() if t.enabled]

    def sync_generation(self, specs: Sequence[ToolSpec], *, owner: str) -> dict[str, int]:
        """世代同步（持锁）：旧代（同 ``owner``）全量卸下 ↔ 新代全量登记。

        两相式纪律：**先整体校验新代**，任何一条非法就整代拒绝、旧代原样保留
        （工具面不空窗）；都合法才卸旧装新。返回 `{"registered": n,
        "unregistered": m}`。供动态工具提供方（mcp）经 `tools.sync_generation`
        总线服务调用——server 断线把它的工具撤下，`tools/list_changed` 换新目录。
        """
        with self._lock:
            for spec in specs:
                if (
                    not isinstance(spec.name, str)
                    or not spec.name.strip()
                    or not callable(spec.fn)
                    or not isinstance(spec.parameters, dict)
                ):
                    raise ValueError(f"新代存在非法声明：{spec!r}")
            old = {k: v for k, v in self._tools.items() if v.owner == owner}
            for name in old:
                del self._tools[name]
            try:
                for spec in specs:
                    self.register_spec(spec)
            except Exception:
                for name, tool in old.items():
                    self._tools[name] = tool
                raise
            return {"registered": len(specs), "unregistered": len(old)}

    def execute(self, name: str, arguments: dict, *, context: str | None = None) -> str:
        """执行工具，返回文本形式的结果。

        工具不存在 / 参数不匹配 / 执行抛错时，都返回人类可读的错误文本
        （宽容降级：模型会读到错误并自己决定下一步）。
        context：agent loop 传入的对话文本，仅注入给声明 needs_context 的工具
        （http_request 用它做 URL 来源校验）。
        """
        tool = self._tools.get(name)
        if tool is None:
            return f"[工具 {name} 未注册，无法执行]"
        try:
            if tool.needs_context:
                result = tool.fn(**arguments, _context=context)
            else:
                result = tool.fn(**arguments)
        except TypeError as e:
            return f"[工具 {name} 调用失败，参数不匹配: {e}]"
        except Exception as e:  # noqa: BLE001 —— 工具实现错误统一降级
            return f"[工具 {name} 执行失败: {e}]"
        return self._stringify(result)

    @staticmethod
    def _stringify(result: Any) -> str:
        """把任意结果转成文本（dict/list 序列化为 JSON）。"""
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)


def _record_failure(registry: ToolRegistry, provider: str, error: str | Exception) -> None:
    """记录一个探询失败：状态进 registry 持久清单，日志留时间线。"""
    message = str(error)
    registry.declaration_failures.append((provider, message))
    logger.warning(f"工具声明探询失败：{provider} -> {message}")


def register_declared_tools(registry: ToolRegistry) -> None:
    """探询各模块的 `<模块名>.ai_tools` 声明并收编进 registry。

    behavior 只认契约不认识模块：按 `services()` 的 `.ai_tools` 后缀搜索。
    应在组装根 import 完全部所有者模块之后调用（时序由 serve.assemble 保证），
    提供方声明必须廉价（只构造 ToolSpec，不联网 / 不建长连接）。

    失败宽容降级：单提供方失败不连坐不炸启动，逐条记 warning 并写入
    `registry.declaration_failures`（供 WebUI / CLI 展示）。
    """
    registry.declaration_failures = []
    for name in services():
        if not name.endswith(DECLARATION_SUFFIX):
            continue
        try:
            specs = call(name)
        except Exception as exc:  # noqa: BLE001 —— 单提供方失败不连坐
            _record_failure(registry, name, exc)
            continue
        if specs is None:
            _record_failure(registry, name, "服务返回 None（无声明）")
            continue
        if isinstance(specs, ToolSpec):
            specs = [specs]
        if not isinstance(specs, (list, tuple)):
            _record_failure(registry, name, f"返回类型不是 ToolSpec 列表：{type(specs).__name__}")
            continue
        for spec in specs:
            try:
                registry.register_spec(spec)
            except ValueError as exc:
                _record_failure(registry, name, f"畸形声明：{exc}（{spec!r}）")


__all__ = [
    "DECLARATION_SUFFIX",
    "RegisteredTool",
    "ToolRegistry",
    "register_declared_tools",
]
