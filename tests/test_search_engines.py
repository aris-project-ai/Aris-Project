"""第三程搜索引擎池用例：冷却 / 失败元数据 / exa 门控与解析 / 渲染收档。

引擎真实 HTTP 已由 test_web_migrate.py 覆盖（bing / tavily 各自的请求细节）；
本文件聚焦 train-3 重整引入的新语义（docs/forAiDoc/BEHAVIOR-REWORK.md §3）：
- EngineFailure 带 provider；429 解析 retry-after → 冷却，冷却中的引擎跳过；
- attempt_search 的 prior_failures（成功前已折的引擎如实上报）；
- exa 经 mcp 模块接入：server 未连接就缺席；markdown 回包解析成 Result；
- 渲染层：无链接条目不进 RECENT_RESULTS（web_open 的点开依据只收可点开的）。
"""

from __future__ import annotations

import json

import pytest

from aris.behavior.search import base
from aris.behavior.search.engines import EngineFailure, Result, exa_search
from aris.behavior.search.render import RECENT_RESULTS, render_results
from aris.behavior.tools import web_search


@pytest.fixture
def no_exa(monkeypatch) -> None:
    """所有用例默认 exa 缺席（不依赖 mcp 状态），需要时再单独打开。"""
    monkeypatch.setattr(base, "exa_available", lambda: False)


def test_engine_failure_carries_provider() -> None:
    """失败元数据：provider 必带；retry-after 可选挂载。"""
    exc = EngineFailure("bing", "HTTP 429", status=429).with_retry_after("120")
    assert exc.provider == "bing"
    assert exc.retry_after == "120"


def test_cooldown_parses_retry_after() -> None:
    """429 数据：retry-after 秒数 → 冷却落表并倒计时；非 429 不冷却。"""
    base._cooldown_until.clear()
    try:
        base.apply_cooldown(
            "tavily", EngineFailure("tavily", "限流", status=429).with_retry_after("120")
        )
        assert base.engine_cooling("tavily") > 0
        base.apply_cooldown("bing", EngineFailure("bing", "超时", status=503))
        assert base.engine_cooling("bing") == 0
        before = base.engine_cooling("tavily")
        # 非 429 不改写冷却窗口（120s 倒计时继续走，时间流逝只会变小但不归零）
        base.apply_cooldown("tavily", EngineFailure("tavily", "又失败但非 429", status=503))
        after = base.engine_cooling("tavily")
        assert 0 < after <= before
    finally:
        base._cooldown_until.clear()


def test_attempts_skip_cooling_engine(monkeypatch) -> None:
    """冷却中的引擎跳过并在 prior_failures 里说明缺席原因。"""
    base._cooldown_until["bing"] = float("inf")  # 让 bing 一直冷却
    try:
        engines = {
            "bing": lambda q, count, timeout: [],
            "tavily": lambda q, count, timeout: [Result(url="https://x", title="T")],
        }
        monkeypatch.setattr(base, "our_engines", lambda: engines)
        monkeypatch.setattr(base.search_config, "prefer_engine", "bing")

        provider, results, prior = base.attempt_search("查询")
        assert provider == "tavily"
        assert results[0].url == "https://x"
        assert prior and prior[0][0] == "bing" and prior[0][1].startswith("冷却中")
    finally:
        base._cooldown_until.clear()


def test_prior_failures_reported_on_success(monkeypatch) -> None:
    """prefer 引擎折了 → 兜底引擎成功，成功结果携带 prior_failures。"""
    engines = {
        "bing": lambda q, count, timeout: (_ for _ in ()).throw(
            EngineFailure("bing", "无搜索结果")
        ),
        "tavily": lambda q, count, timeout: [Result(url="https://y", title="兜底")],
    }
    monkeypatch.setattr(base, "our_engines", lambda: engines)
    monkeypatch.setattr(base.search_config, "prefer_engine", "bing")

    payload = json.loads(web_search._do_web_search("测试"))
    assert payload["engine"] == "tavily"
    failed = payload.get("failed") or []
    assert {"provider": "bing", "error": "无搜索结果"} in failed


def test_exa_gated_by_mcp_status(monkeypatch) -> None:
    """exa 引擎要 mcp server 已连接才进尝试表（未配置城市缺席）。"""
    engines = base.our_engines()
    assert "exa" not in engines

    monkeypatch.setattr(base, "exa_available", lambda: True)
    assert "exa" in base.our_engines()


def test_exa_search_parses_markdown(monkeypatch) -> None:
    """mcp.call_tool 返回 markdown → 解析成 Result 列表（标题 / 链接 / 摘要）。"""

    def _fake_call(name, server, tool, args):
        assert (server, tool) == (base.EXA_MCP_SERVER, base.EXA_TOOL_NAME)
        assert args["query"] == "量子计算"
        return (
            "1. [量子计算的进展](https://exa.example/a) — 量子比特数 ascending!\n"
            "2. [Next](https://exa.example/b) – 后续摘要"
        )

    monkeypatch.setattr("aris.behavior.search.engines.call", _fake_call)
    results = exa_search("量子计算", count=2, timeout=1.0)

    assert [r.url for r in results] == ["https://exa.example/a", "https://exa.example/b"]
    assert results[0].title == "量子计算的进展"
    assert "ascending" in results[0].content


def test_exa_search_without_links_degrades_to_one_result(monkeypatch) -> None:
    """回包没有链接（全文本）→ 整块当一条无 url 的 Result（web_open 点不了）。"""
    monkeypatch.setattr(
        "aris.behavior.search.engines.call",
        lambda *a, **k: "纯文本摘要：没有 markdown 链接结构的输出。",
    )
    results = exa_search("q", count=1, timeout=1.0)

    assert len(results) == 1
    assert results[0].url == ""
    assert "纯文本摘要" in results[0].content


def test_render_records_only_openable() -> None:
    """渲染：有 url 收档 RECENT_RESULTS；无链接条目不收档。"""
    try:
        RECENT_RESULTS.clear()
        markdown = render_results(
            [
                Result(url="https://a", title="A", content="摘要A", published="2026-01-01"),
                Result(title="无链接", content="纯文本"),
                Result(url="https://b", title=""),
            ]
        )
        assert "1. [A](https://a)" in markdown
        assert "（发布时间：2026-01-01）" in markdown
        assert "3. [https://b](https://b)" in markdown  # 无标题条目落 url 当标题
        assert set(RECENT_RESULTS) == {1, 3}
        assert RECENT_RESULTS[1]["url"] == "https://a"
    finally:
        RECENT_RESULTS.clear()


def test_all_failed_json_includes_providers(monkeypatch) -> None:
    """全引擎失败：错误 JSON 带 failed 元数据（谁出的错一清二楚）。"""

    def _boom(q, count, timeout):
        raise EngineFailure("bing", "HTTP 503 爆炸", status=503)

    def _tav(q, count, timeout):
        raise EngineFailure("tavily", "无搜索结果")

    engine_table = {"bing": _boom, "tavily": _tav}
    monkeypatch.setattr(base, "our_engines", lambda: engine_table)
    monkeypatch.setattr(base.search_config, "prefer_engine", "bing")

    payload = json.loads(web_search._do_web_search("查询"))
    assert payload["type"] == "web_search_error"
    providers = {f["provider"] for f in payload.get("failed", [])}
    assert providers == {"bing", "tavily"}
