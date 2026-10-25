"""内置工具：web_search / web_open —— 联网搜索与网页正文读取（壳层）。

搜索走多引擎池（2026-10-25 重整，详见 docs/forAiDoc/WEB-SEARCH.md「第三程重整」）：
**Bing 直连为主 + Tavily（keyed / keyless）兜底 + Exa（mcp 型端点）**。
引擎住在 `behavior/search/`（只吐归一化 Result），本文件只做三件事：
- 渲染（markdown 省 token，外层 JSON 标识）；
- 把引擎失败的 provider 元数据如实转给模型（`failed` 字段）；
- web_open 的 id → url 点开约定。

返回格式（模型可见面，与旧版兼容）：
    {"type": "web_search_results", "query": "...", "engine": "bing|tavily|exa",
     "results": "1. [标题](url)\\n   摘要\\n2. ...", "failed": [...]?}
每条结果自带自增 id（第 1 条为 1），同时写入 `search.RECENT_RESULTS`
（id→url 收档），web_open 按 id 点开读正文：
    {"type": "web_open_result", "id": 2, "url": "...",
     "content": "标题 + 原文链接 + 正文（截断省 token）"}

失败策略（宽容降级）：所有引擎失败返回错误 JSON（含每家的失败原因），
不抛到 UI（registry.execute 也会兜底）；429 冷却由 search.base 统一收管。

HTTP 传输统一走 core.http（`core.call("http.request", ...)`）；Bing 的
「先访问首页拿 cookie 再搜索」由引擎层用命名会话（session="bing"）保证
cookie 连续。旧全量实现要考古走 git 历史（297abf1 之前的版本）。
"""

from __future__ import annotations

import json
from enum import StrEnum

from loguru import logger

from ..registry import ToolRegistry
from ..search import (
    RECENT_RESULTS,
    SearchAllFailed,
    attempt_search,
    render_results,
    search_config,
)

# 历史符号（旧用例 / 调试引用）：指向 search 包内的共享实现（同一份对象）
from ..search.engines import BING_UA as _BING_UA  # noqa: F401
from .web_common import extract_page

_search_config = search_config
_recent_results = RECENT_RESULTS


class WebSearchResultType(StrEnum):
    """联网搜索工具返回结果的外层标识。"""

    RESULTS = "web_search_results"  # 搜索成功
    ERROR = "web_search_error"  # 搜索失败（宽容降级）


class WebOpenResultType(StrEnum):
    """web_open 工具返回结果的外层标识。"""

    RESULT = "web_open_result"  # 正文读取成功
    ERROR = "web_open_error"  # 读取失败（宽容降级）


def _do_web_search(query: str) -> str:
    """执行一次联网搜索（引擎池按序尝试），返回 JSON 文本结果。"""
    try:
        provider, results, prior = attempt_search(query)
    except SearchAllFailed as exc:
        logger.info(f"所有搜索引擎失败：{exc}")
        return json.dumps(
            {
                "type": WebSearchResultType.ERROR,
                "query": query,
                "error": f"所有搜索引擎均失败：{exc}",
                "failed": [{"provider": p, "error": r} for p, r in exc.failures],
            },
            ensure_ascii=False,
        )
    markdown = render_results(results)
    payload: dict[str, object] = {
        "type": WebSearchResultType.RESULTS,
        "query": query,
        # engine 字段如实标识结果来源
        "engine": provider,
        "results": markdown,
    }
    if prior:
        # 附加字段（增量）：本轮前面谁试过但失败，模型与 WebUI 都知道谁出的错
        payload["failed"] = [{"provider": p, "error": r} for p, r in prior]
    return json.dumps(payload, ensure_ascii=False)


def _do_web_open(result_id: int) -> str:
    """按搜索结果 id 抓取并提取正文，返回 markdown；失败抛异常。"""
    entry = RECENT_RESULTS.get(result_id)
    if entry is None:
        raise RuntimeError(f"id {result_id} 不在最近的搜索结果里（需要先 web_search，且 id 有效）")
    url = entry["url"]
    from aris.core import call

    resp = call("http.request", "GET", url, timeout=search_config.webopen_timeout_seconds)
    if resp is None:
        raise RuntimeError("core 未注册 http.request 服务")
    if resp.status >= 400:
        raise RuntimeError(f"HTTP {resp.status}")

    # trafilatura（web_common.extract_page，bs4 兜底）：过滤导航/页脚/广告
    body = extract_page(resp.text, url=url)
    if not body:
        raise RuntimeError(f"网页正文提取为空（可能是动态渲染页面）：{url}")
    body = body.strip()
    if len(body) > search_config.webopen_max_chars:
        body = body[: search_config.webopen_max_chars] + "…"

    title = entry.get("title") or url
    return f"# {title}\n\n原文链接：{url}\n\n{body}"


def _do_web_open_result(result_id: int) -> str:
    """执行一次 web_open，返回完整结果（外层 JSON + 内部 markdown）。"""
    try:
        markdown = _do_web_open(result_id)
    except Exception as e:  # noqa: BLE001 —— 读取失败宽容降级为错误文本
        return json.dumps(
            {
                "type": WebOpenResultType.ERROR,
                "id": result_id,
                "error": f"网页读取失败：{e}",
            },
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "type": WebOpenResultType.RESULT,
            "id": result_id,
            "content": markdown,
        },
        ensure_ascii=False,
    )


def register(registry: ToolRegistry) -> None:
    """向 registry 注册 web_search 与 web_open 工具（schema 与旧版一致）。"""

    def _fn(query: str) -> str:
        return _do_web_search(query)

    registry.register(
        "web_search",
        description=(
            "联网搜索。当用户询问实时信息、需要查资料时使用。"
            "参数 query 为搜索关键词。返回搜索结果列表，每条带 id，"
            "可用 web_open 按 id 点开读正文。"
        ),
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词，尽量简洁准确"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        fn=_fn,
    )

    def _open_fn(id: int) -> str:
        return _do_web_open_result(id)

    registry.register(
        "web_open",
        description=(
            "读取某条搜索结果（web_search 返回的 id）的网页正文。"
            "当搜索结果摘要不够、需要看完整内容时使用。"
            "参数 id 必须是最近一次 web_search 返回结果里的 id。"
            "返回标题 + 原文链接 + 正文（截断）。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer",
                    "description": "搜索结果条目的 id（web_search 返回，从 1 开始）",
                },
            },
            "required": ["id"],
            "additionalProperties": False,
        },
        fn=_open_fn,
    )
