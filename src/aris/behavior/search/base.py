"""搜索引擎池基础设施：归一化 Result、失败元数据、冷却与尝试循环。

引擎池定案（2026-10-25，抄 opencode 形状去掉多 KV；演进史见 WEB-SEARCH.md）：

- 引擎只吐归一化 `Result`（url / title / content / published），**壳层
  （tools/web_search.py）统一渲染 markdown**——引擎不做格式化；
- `EngineFailure` 自带 `provider` 元数据（模型与 WebUI 都知道谁出的错）；
- **429 冷却**：HTTP 429 时解析 `retry-after`，冷却中的引擎直接跳过；
- **attempted 防回环**：单次查询内每个引擎只试一次（我们没有跨会话状态设施，
  不做 KV / 会话亲和）。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC

from loguru import logger

from aris.infra.toml import load_config

# ── 引擎清单与首选顺序 ──
# 名称同时是 data/config/search.toml prefer_engine 的合法值与输出 JSON engine 字段的值
ENGINES = ("bing", "tavily", "exa")
# prefer_engine 未知值的兜底
_DEFAULT_ENGINE = "bing"
# 429 无 retry-after（或解析失败）时的默认冷却秒数
COOLDOWN_DEFAULT_SECONDS = 60.0


@dataclass
class Result:
    """一条归一化搜索结果（引擎产出，壳层渲染）。

    url 为空 = 该条没有可点开的链接（如 Exa 出纯文本摘要），web_open 不收它。
    """

    url: str = ""
    title: str = ""
    content: str = ""
    # 发布时间（引擎给得出就填，如 Tavily publishedDate / Bing 日期标签）
    published: str = ""


class EngineFailure(Exception):
    """单引擎失败（带 provider 元数据，供壳层与错误 JSON 归档）。"""

    def __init__(self, provider: str, reason: str, *, status: int = 0) -> None:
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason
        self.status = status
        # 429 时由引擎顺手带上响应头里的原始 retry-after（秒数或 HTTP 日期串）
        self.retry_after: str | None = None

    def with_retry_after(self, raw: str | None) -> EngineFailure:
        self.retry_after = raw
        return self


class SearchAllFailed(Exception):
    """全部引擎失败；failures 是 [(provider, 原因)]，壳层转成错误 JSON。"""

    def __init__(self, failures: list[tuple[str, str]]) -> None:
        text = "；".join(f"{provider}（{reason}）" for provider, reason in failures)
        super().__init__(text or "没有可用引擎")
        self.failures = failures


@dataclass
class SearchConfig:
    """联网搜索可调参数（data/config/search.toml；shell 与引擎共用）。

    prefer_engine：首选引擎，"bing" / "tavily" / "exa" / "auto"
    （auto = 按查询语言分流，含中文走 Tavily——2026-08-14 备选方案，默认已回 bing）。
    """

    prefer_engine: str = "bing"
    timeout_seconds: float = 15.0
    results_count: int = 5
    snippet_max_len: int = 200
    webopen_timeout_seconds: float = 20.0
    webopen_max_chars: int = 4000


# 模块级单例：web_search 壳层的历史符号 `_search_config` 指向它（测试与 toml 覆写共享同一份）
search_config = load_config(SearchConfig(), "search.toml")

# → Exa 引擎走总线 mcp.call_tool，server 名固定为 data/config/mcp.toml 里的 "exa"
EXA_MCP_SERVER = "exa"
# mcp.exa.ai 的搜索工具名（免 key 端点，免不了万一改名，失败会降级到其他引擎）
EXA_TOOL_NAME = "web_search_exa"

# 冷却表：provider → 解禁时刻（monotonic）；进程内状态，重启即清
_cooldown_until: dict[str, float] = {}


def engine_cooling(provider: str) -> float:
    """该引擎还在冷却多久（0 = 不冷却）。

    供壳层把「冷却跳过」也记进 failures 元数据，模型能看到引擎为何缺席。
    """
    until = _cooldown_until.get(provider, 0.0)
    return max(0.0, until - time.monotonic())


def apply_cooldown(provider: str, failure: EngineFailure) -> None:
    """按失败元数据写冷却：429 → 解析 retry-after（缺省 COOLDOWN_DEFAULT_SECONDS）。"""
    if failure.status != 429:
        return
    seconds = _parse_retry_after(failure.retry_after) or COOLDOWN_DEFAULT_SECONDS
    _cooldown_until[provider] = time.monotonic() + seconds
    logger.warning(f"搜索引擎 {provider} 被限流（429），冷却 {seconds:.0f}s")


def _parse_retry_after(raw: str | None) -> float | None:
    """解析 retry-after 头：秒数（"120"）或 HTTP 日期（RFC 7231）两种格式。"""
    if not raw:
        return None
    raw = raw.strip()
    try:
        return float(raw)
    except ValueError:
        pass
    try:
        from datetime import datetime
        from email.utils import parsedate_to_datetime

        when = parsedate_to_datetime(raw)
        if isinstance(when, datetime):
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            # parsedate_to_datetime 在 3.13 内部用 system tz 修正存在争议，算差值即可
            return max(0.0, (when - datetime.now(tz=UTC)).total_seconds())
    except Exception:  # noqa: BLE001 —— 头格式千奇百怪，解析失败就按缺省冷却
        return None
    return None


def ordered_engines(query: str) -> list[tuple[str, Callable[..., list[Result]]]]:
    """决定引擎尝试顺序：prefer 先行，其余按 ENGINES 清单次序兜底。

    exa 需经 mcp 模块接入——server 未配置 / 未连接时**不进尝试序列**
    （否则每轮搜索都白等）。
    """
    from .base import our_engines

    preferred = search_config.prefer_engine
    if preferred == "auto":
        preferred = "tavily" if _has_cjk(query) else _DEFAULT_ENGINE
    elif preferred not in ENGINES:
        logger.warning(f"未知 prefer_engine={preferred!r}，回退 {_DEFAULT_ENGINE}")
        preferred = _DEFAULT_ENGINE

    available = our_engines()
    order = [preferred] + [name for name in ENGINES if name != preferred]
    out: list[tuple[str, Callable[..., list[Result]]]] = []
    for name in order:
        fn = available.get(name)
        if fn is not None:
            out.append((name, fn))
    return out


def _has_cjk(text: str) -> bool:
    """是否含中日韩统一表意文字（auto 分流用；历史定案见旧实现注释）。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def attempt_search(query: str) -> tuple[str, list[Result], list[tuple[str, str]]]:
    """按序尝试引擎，成功即返回 ``(provider, results, prior_failures)``。

    - 冷却中的引擎跳过（缺席原因记进 failures，模型可见）；
    - 单次查询内每个引擎只试一次（attempted 防回环）；
    - 全部失败抛 `SearchAllFailed`（壳层转错误 JSON，宽容降级）；
    - 成功时 ``prior_failures`` 是排在前面已被尝试失败的引擎记录
      [(provider, 原因)]，壳层照样如实标注「谁试过但折了」。
    """
    attempted: set[str] = set()
    failures: list[tuple[str, str]] = []
    count = search_config.results_count
    timeout = search_config.timeout_seconds

    for provider, fn in ordered_engines(query):
        if provider in attempted:  # pragma: no cover —— ordered_engines 不会重复
            continue
        attempted.add(provider)
        remaining = engine_cooling(provider)
        if remaining > 0:
            failures.append((provider, f"冷却中（剩 {remaining:.0f}s）"))
            continue
        try:
            results = fn(query, count=count, timeout=timeout)
        except EngineFailure as exc:
            failures.append((provider, exc.reason))
            apply_cooldown(provider, exc)
            continue
        except Exception as exc:  # noqa: BLE001 —— 任何引擎内部失败都不连坐
            failures.append((provider, str(exc) or type(exc).__name__))
            continue
        if not results:
            failures.append((provider, "无搜索结果"))
            continue
        return provider, results, failures
    raise SearchAllFailed(failures)


# ── 引擎可用性门控 ──


def our_engines() -> dict[str, Callable[..., list[Result]]]:
    """当前可用的引擎表（冷却判定在 attempt_search，不在此处）。"""
    from .engines import bing_search, exa_search, tavily_search

    engines: dict[str, Callable[..., list[Result]]] = {
        "bing": bing_search,
        "tavily": tavily_search,
    }
    if exa_available():
        engines["exa"] = exa_search
    return engines


def exa_available() -> bool:
    """Exa 经第二程的 mcp 模块接入；server 已配置且已连接才可用。"""
    from aris.core import call, has_service

    if not has_service("mcp.status"):  # mcp 未装配 = 引擎缺席（不挂 error 日志噪音）
        return False
    try:
        info: dict[str, object] = call("mcp.status") or {}
    except Exception:  # noqa: BLE001 —— mcp 装了但坏了 = 引擎缺席，不给主链路添堵
        return False
    servers = (info.get("servers") or {}) if isinstance(info, dict) else {}
    state = servers.get(EXA_MCP_SERVER) or {}
    return state.get("status") == "已连接"
