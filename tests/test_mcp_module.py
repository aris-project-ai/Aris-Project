"""mcp 模块测试：世代同步（注册表侧）+ stdio 全链路（真实子进程 server）。

- 世代同步不真连 MCP：直接用假 ToolSpec 验证「旧代卸下 ↔ 新代装上 / 失败保旧代」；
- stdio 链路用官方 SDK 的 MCPServer 起一个真实子进程（tests/support/mcp_echo_server.py），
  走完 配置 → 连接 → 目录 → 声明 → registry 执行 → 结果归一化 全程。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from aris.behavior.registry import ToolRegistry
from aris.core.tools import ToolSpec
from aris.mcp.conf import McpConfig, McpServerConfig
from aris.mcp.runtime import McpRuntime, MCPToolError, _humanize

SUPPORT = Path(__file__).parent / "support"


def _spec(name: str, owner: str = "mcp", **extra: Any) -> ToolSpec:
    """构造最小声明（fn 原样回显调用参数）。"""

    def fn(**kwargs: Any) -> Any:
        return kwargs

    return ToolSpec(
        name=name,
        description=f"{name}：测试用",
        parameters={"type": "object", "properties": {}},
        fn=fn,
        owner=owner,
        **extra,
    )


# ---------- 世代同步（registry 侧，不真连） ----------


def test_sync_generation_swaps_owner_set() -> None:
    """旧代（同 owner）全量卸下 ↔ 新代全量装上；别的 owner 不受波及。"""
    reg = ToolRegistry()
    reg.register_spec(_spec("mcp_a_old", owner="mcp"))
    reg.register_spec(_spec("builtin_x", owner="behavior"))

    outcome = reg.sync_generation(
        [_spec("mcp_a_new", owner="mcp"), _spec("mcp_b_new", owner="mcp")], owner="mcp"
    )

    names = {t.definition.name for t in reg.items()}
    assert names == {"mcp_a_new", "mcp_b_new", "builtin_x"}
    assert outcome == {"registered": 2, "unregistered": 1}


def test_sync_generation_keeps_old_on_invalid_spec() -> None:
    """新代里混入非法声明 → 整代拒绝，旧代原样保留（工具面不空窗）。"""
    reg = ToolRegistry()
    reg.register_spec(_spec("mcp_a_old", owner="mcp"))
    bad = ToolSpec(name="", description="", parameters={"type": "object"}, fn=None, owner="mcp")

    with pytest.raises(ValueError):
        reg.sync_generation([_spec("mcp_a_new", owner="mcp"), bad], owner="mcp")

    assert [t.definition.name for t in reg.items()] == ["mcp_a_old"]


def test_sync_generation_empty_drops_all_owner() -> None:
    """空新代 = 该 owner 的工具全部撤下（server 全断线的情形）。"""
    reg = ToolRegistry()
    reg.register_spec(_spec("mcp_a", owner="mcp"))
    reg.register_spec(_spec("knowledge_search", owner="knowledge"))

    reg.sync_generation([], owner="mcp")

    assert [t.definition.name for t in reg.items()] == ["knowledge_search"]


# ---------- 人话映射 ----------


def test_humanize_maps_common_http_errors() -> None:
    """429 → 限流；401/403 → 鉴权失败（AGENTS §6：HTTP 报错给人话）。"""
    assert "限流" in _humanize(RuntimeError("mcp error: 429 too many requests"))
    assert "鉴权" in _humanize(RuntimeError("401 unauthorized"))
    assert "鉴权" in _humanize(RuntimeError("HTTP 403 Forbidden"))
    assert _humanize(RuntimeError("boom")) == "boom"


# ---------- stdio 全链路（真实子进程 server） ----------


@pytest.fixture
def echo_registry(tmp_path: Path) -> ToolRegistry:
    """连上真实回显 server 的注册表（声明收编 + 世代同步后可用）。"""
    runtime = McpRuntime(
        McpConfig(
            servers={
                "testserver": McpServerConfig(
                    transport="stdio",
                    command=sys.executable,
                    args=[str(SUPPORT / "mcp_echo_server.py")],
                )
            }
        ),
        tmp_path,
    )
    reg = ToolRegistry()
    reg.sync_generation(runtime.catalog_specs(), owner="mcp")
    yield reg
    runtime.stop()


def test_stdio_catalog_and_call(echo_registry: ToolRegistry) -> None:
    """全链路：目录收编后，echo 工具执行返回归一化文本。"""
    names = {t.definition.name for t in echo_registry.items()}
    assert names == {"mcp_testserver_echo", "mcp_testserver_boom"}
    assert all(t.owner == "mcp" for t in echo_registry.items())

    out = echo_registry.execute("mcp_testserver_echo", {"text": "hi"})
    assert out == "echo:hi"


def test_stdio_tool_error_degrades(echo_registry: ToolRegistry) -> None:
    """服务端报错仍降级为文本（boom → RuntimeError 信息传递出来）。"""
    out = echo_registry.execute("mcp_testserver_boom", {})
    assert "boom" in out
    assert out.startswith("[工具")  # registry 层的降级文案


def test_stdio_unknown_server(tmp_path: Path) -> None:
    """未配置的 server 调用 → 可读错误，不裸崩。"""
    runtime = McpRuntime(McpConfig(), tmp_path)
    try:
        with pytest.raises(MCPToolError):
            runtime.call_tool_sync("nope", "tool", {})
    finally:
        runtime.stop()
