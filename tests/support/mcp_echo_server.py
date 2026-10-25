"""最小型 MCP stdio server（供 tests/test_mcp_module.py 拉起）。

用官方 SDK v2 的 MCPServer 实现：一个回显工具 + 一个必定失败的工具，
覆盖「正常调用 / 服务端报错 / 目录列表」三条路径。
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

server = MCPServer("echo-server")


@server.tool()
def echo(text: str) -> str:
    """原样回显输入文本（测试用）。"""
    return f"echo:{text}"


@server.tool()
def boom() -> str:
    """总会失败的工具（测试服务端报错路径）。"""
    msg = "boom!"
    raise RuntimeError(msg)


if __name__ == "__main__":
    server.run()
