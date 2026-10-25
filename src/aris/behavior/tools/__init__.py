"""内置工具集：统一入口注册 behavior 自家的工具。

业务模块的 agent 工具**不在此处**塞壳——各自在模块内经
`<模块名>.ai_tools` 总线服务声明（`core/tools.py: ToolSpec` 契约），
由 `behavior.registry.register_declared_tools` 在装配时探询收编。
"""

from __future__ import annotations

from ..registry import ToolRegistry
from . import get_current_time, http_request, web_search


def register_builtin_tools(registry: ToolRegistry) -> None:
    """把 behavior 自家的内置工具注册进给定 registry。"""
    get_current_time.register(registry)
    http_request.register(registry)
    web_search.register(registry)
