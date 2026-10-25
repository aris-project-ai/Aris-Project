"""behavior 模块 —— 行为编排。

对外暴露：
- BehaviorRuntime：进程级运行时（工具注册表 + 技能管理器 + agent loop）
- ToolRegistry：工具注册表（工具统一注册/执行入口）
- AgentLoop：agent loop（LLM ↔ 工具执行循环）
- register_builtin_tools：注册 behavior 自家内置工具
- register_declared_tools：探询收编各模块经 `<模块名>.ai_tools` 声明的工具
"""

from .loop import AgentLoop, LoopEvent, LoopEventType
from .registry import (
    RegisteredTool,
    ToolRegistry,
    register_declared_tools,
)
from .runtime import BehaviorRuntime
from .tools import register_builtin_tools

__all__ = [
    "AgentLoop",
    "BehaviorRuntime",
    "LoopEvent",
    "LoopEventType",
    "RegisteredTool",
    "ToolRegistry",
    "register_builtin_tools",
    "register_declared_tools",
]
