"""跨模块工具契约（CMCB 边界载荷）。

业务模块想给 agent 面加工具（如 knowledge 的 `knowledge_search`），不在
behavior 里塞壳，而是在自家 `tools.py` 构造 ToolSpec 声明，经总线服务
`<模块名>.ai_tools` 提供；behavior 装配时统一探询收编进 ToolRegistry
（AGENTS.md §6 CMCB）。工具的 fn 本身不 provide 成总线服务——总线只传
声明，执行由 registry 持有，agent loop 经 `tools.execute` 执行。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# 工具执行函数：接收关键字参数（已由模型按 schema 填好），返回任意可序列化结果；
# needs_context 的工具会额外收到 `_context`（agent loop 拼好的对话文本）
ToolFn = Callable[..., Any]


@dataclass(frozen=True)
class ToolSpec:
    """一个 agent 工具的声明（业务模块填写，behavior 收编）。

    声明必须廉价：`.ai_tools` 服务只应构造本结构，不联网、不建长连接。

    enabled：声明方按自身配置给的状态（如 knowledge 的 ``enabled``）。
    False 时照常登记进 registry（CLI / WebUI 可见、可展示状态），
    但 `definitions()` 会过滤——模型在请求里看不到该工具。
    """

    name: str
    description: str
    parameters: dict[str, Any]
    fn: ToolFn
    owner: str  # 声明方模块名，WebUI 工具页展示与后续「工具开关」用
    needs_context: bool = False
    enabled: bool = True


__all__ = ["ToolFn", "ToolSpec"]
