"""mcp 工具汇总：远端 server 目录 → `ToolSpec` 声明 + 结果归一化。

工具名命名 `mcp_<server>_<tool>`：server 名有 ``[a-z0-9_-]`` 约束、工具名
按 MCP 约定只含安全字符，前缀化让 mcp 工具永不与内置 / 技能 / 业务工具撞名。
工具文案（description / schema）是远端 server 写的——**mcp 不二次人味化**，
只做结构搬运（AGENTS.md §6：工具文案不拟人）。

执行 fn 闭包注册到 registry 后由 agent loop 经 ``tools.execute`` 调用，
同模块内部走 ``McpRuntime.call_tool_sync``（不过总线，AGENTS §6 边界）。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..core.tools import ToolSpec

if TYPE_CHECKING:
    import mcp.types as mcp_types


# 工具名的长度与字符白名单：超出的远端工具在 spec 构造处抛错，整个声明被丢弃
_TOOL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def spec_from_tool(
    server: str, tool: mcp_types.Tool, runner: Callable[[str, dict], str]
) -> ToolSpec:
    """把远端 Tool 转成本地 ToolSpec 声明（名字 / schema 不合法会抛 ValueError）。

    ``runner``： ``(tool_name, arguments) -> str``——registry 会把模型的参数
    dict 展开成 kwargs 调 fn，这里再原样收拢传回 runner（MCP 协议要的就是
    arguments dict，不做二次拆装）。
    """
    if not _TOOL_NAME_RE.match(tool.name or ""):
        raise ValueError(f"远端工具名不合法：{tool.name!r}")
    schema = tool.input_schema if isinstance(tool.input_schema, dict) else None
    if schema is None:
        raise ValueError(f"远端工具 {tool.name} 的 inputSchema 不是对象")

    def fn(**kwargs: Any) -> str:
        return runner(tool.name, kwargs)

    return ToolSpec(
        name=f"mcp_{server}_{tool.name}",
        description=tool.description or "",
        parameters=dict(schema),
        fn=fn,
        owner="mcp",
    )


__all__ = ["spec_from_tool"]
