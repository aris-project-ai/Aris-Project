"""mcp 模块 —— 通用 MCP 客户端（一个客户端接所有 server）。

定位：官方 ``mcp`` SDK +
配置驱动 transport（stdio / streamable-http），SDK 跑在专属 owner 线程
（AstrBot owner-task 模式搬线程），对外只给**同步**服务。Exa 这类 MCP 型
搜索端点不走手写适配，直接配置接进来（第三程联网搜索依赖本模块）。

总线服务：
- ``mcp.ai_tools`` —— agent 工具声明（`.ai_tools` 契约；触发连接 + 目录拉取，
  失败的 server 不连坐：状态进 ``mcp.status``，工具从声明里缺席）
- ``mcp.call_tool`` —— 执行一次 MCP 工具调用（文本归一化 + 失败人话）
- ``mcp.status`` —— 状态快照（供 serve 探针 / 将来的 WebUI 工具页）

事件（emit）：
- ``mcp.tools_changed`` —— 目录防抖重拉并世代换装完成后（payload：owner/count）
- 订阅 ``tools.sync_generation`` 的是 behavior 的注册表（世代换装的落点）

配置：`data/config/mcp.toml`（server 表 + 三组超时 + 退避参数），密钥只写
环境变量名、值进 data/config/secrets.toml；缺文件 = 未接任何 server（模块零开销）。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from loguru import logger

from ..core import provide
from ..infra.settings import get_settings
from .conf import McpConfig, McpServerConfig, get_mcp_config
from .runtime import McpRuntime, MCPToolError


@lru_cache
def get_runtime() -> McpRuntime:
    """模块级唯一运行时（未配 server 时是零开销的空运行时）。"""
    settings = get_settings()
    runtime = McpRuntime(get_mcp_config(), settings.data_dir)
    return runtime


def _tool_specs() -> list[Any]:
    """总线服务：agent 工具声明（`.ai_tools` 契约；触发连接触发冷启动）。

    接线失败的 server 不连坐：它缺席本次声明，状态面在 ``mcp.status`` 查。
    """
    runtime = get_runtime()
    if not runtime.status_snapshot()["configured"]:
        return []
    try:
        return runtime.catalog_specs()
    except Exception as exc:  # noqa: BLE001 —— 声明探询层宽容降级（连坐进失败清单）
        logger.warning(f"mcp: 目录声明失败（全量缺席本轮）：{exc}")
        return []


def _call_tool(server: str, tool: str, arguments: dict) -> str:
    """总线服务：执行一次 MCP 工具调用（文本归一化，失败抛 MCPToolError）。"""
    return get_runtime().call_tool_sync(server, tool, arguments)


def _status() -> dict[str, Any]:
    """总线服务：状态快照（不触发连接）。"""
    return get_runtime().status_snapshot()


provide("mcp.ai_tools", _tool_specs)
provide("mcp.call_tool", _call_tool)
provide("mcp.status", _status)

__all__ = [
    "MCPToolError",
    "McpConfig",
    "McpRuntime",
    "McpServerConfig",
    "get_mcp_config",
    "get_runtime",
]
