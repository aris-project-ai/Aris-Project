"""搜索引擎池（第三程）：Bing 直连 / Tavily（keyed + keyless 兜底） / Exa（经 mcp）。

定案与形状详见 base.py 顶部注释；演进史见 docs/forAiDoc/WEB-SEARCH.md：
- 引擎只吐归一化 `Result`，渲染归壳层（`behavior/tools/web_search.py`）；
- 失败带 provider 元数据；429 冷却 + 单查询 attempted 防回环。
"""

from __future__ import annotations

from .base import (
    ENGINES,
    EXA_MCP_SERVER,
    EXA_TOOL_NAME,
    EngineFailure,
    Result,
    SearchAllFailed,
    SearchConfig,
    apply_cooldown,
    attempt_search,
    engine_cooling,
    exa_available,
    ordered_engines,
    search_config,
)
from .render import RECENT_RESULTS, render_results

__all__ = [
    "ENGINES",
    "EXA_MCP_SERVER",
    "EXA_TOOL_NAME",
    "RECENT_RESULTS",
    "EngineFailure",
    "Result",
    "SearchAllFailed",
    "SearchConfig",
    "apply_cooldown",
    "attempt_search",
    "engine_cooling",
    "exa_available",
    "ordered_engines",
    "render_results",
    "search_config",
]
