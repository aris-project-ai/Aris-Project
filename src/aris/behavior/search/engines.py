"""搜索引擎实现：Bing 直连 / Tavily（API key 或 keyless 模式） / Exa（经 mcp）。

引擎契约：``fn(query, count, timeout) -> list[Result]``，失败抛
`EngineFailure`（带 provider 与 HTTP status；429 时顺手带上 retry-after 原值，
冷却由 `base.attempt_search` 统一处理）。渲染不在本层（壳层统一）。
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import urllib.parse

from bs4 import BeautifulSoup
from loguru import logger

from aris.core import call

from .base import EXA_MCP_SERVER, EXA_TOOL_NAME, EngineFailure, Result, search_config

# Tavily API 端点（keyless 复用同端点，头部声明访问模式）
_TAVILY_URL = "https://api.tavily.com/search"
# Tavily keyless 模式声明头名（无 key 时走免费通道）
_TAVILY_KEYLESS_HEADER = "X-Tavily-Access-Mode"

# Bing 搜索用 Firefox UA（无需 sec-ch-ua 配套指纹，实测结果更稳定）
BING_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"


def _clean_snippet(raw: str, max_len: int | None = None) -> str:
    """清洗摘要：HTML 实体解码 + 折叠空白 + 取最长的连续文本块。

    Tavily / Bing 的 content 是页面正文原始片段，常混入导航/元数据噪音
    （实测见「博客园logo / 搜索 / 订阅数」等）。取最长的文本块可
    大概率命中正文主干，省 token 且不给模型添乱。
    ``max_len`` 缺省用配置 snippet_max_len。
    """
    limit = max_len if max_len is not None else search_config.snippet_max_len
    text = html.unescape(raw)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    blocks = [b.strip() for b in text.splitlines() if b.strip()]
    longest = max(blocks, key=len) if blocks else text.strip()
    if len(longest) > limit:
        longest = longest[:limit] + "…"
    return longest


# ── Bing 直连 ──────────────────────────────────────────────


def _decode_bing_redirect(href: str) -> str:
    """解码 Bing /ck/a 重定向链接的 u= 参数（base64 包装 URL）。

    实测格式：`https://www.bing.com/ck/a?...&u=a1<base64(真实URL)>`。
    解码失败返回空串（上层保留原链接，web_open 跟随重定向兜底）。
    """
    if not href.startswith(("https://www.bing.com/ck/a", "/ck/a")):
        return ""
    params = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
    raw = (params.get("u") or [""])[0]
    if not raw:
        return ""
    b64 = raw[2:] if raw.startswith("a1") else raw
    try:
        return base64.urlsafe_b64decode(b64 + "===").decode()
    except Exception:  # noqa: BLE001 —— 解码失败不值得抛错，留原链接即可
        return ""


def _http_raises(provider: str, resp: object | None, *, what: str) -> None:
    """公共防御：core.http 未注册 / HTTP 失败 → EngineFailure（含 status）。"""
    if resp is None:
        raise EngineFailure(provider, "core 未注册 http.request 服务")
    status = getattr(resp, "status", 0)
    if status >= 400:
        retry_after = _retry_after_header(resp)
        failure = EngineFailure(provider, f"HTTP {status}({what})", status=status)
        if retry_after is not None:
            raise failure.with_retry_after(retry_after)
        raise failure


def _retry_after_header(resp: object) -> str | None:
    """取出响应头里的 Retry-After（core.http 的 headers 是全量小写键字典）。"""
    headers = getattr(resp, "headers", None) or {}
    for key, value in headers.items():
        if key.lower().strip() == "retry-after":
            return str(value)
    return None


def bing_search(query: str, *, count: int, timeout: float) -> list[Result]:
    """Bing 网页搜索（无 API key、免费、中文结果好）；失败抛 EngineFailure。

    关键实现细节（2026-08-14 实测，直接影响结果质量）：
    - 用 core.http 命名会话（session="bing"）：先访问首页拿 cookie（MUID 等），
      再搜索；不带 cookie 时 Bing 偶发返回官网首页等低质量结果。
    - 带 form=QBRE 参数（真实浏览器搜索请求带此参数）。
    - UA 用 Firefox（Chrome UA 需配 sec-ch-ua 系列头，否则指纹不完整）。
    - 链接是 /ck/a 重定向包装，解码 u= 参数（base64）拿真实 URL。
    """
    provider = "bing"
    headers = {
        "User-Agent": BING_UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    encoded = urllib.parse.quote(query)
    search_url = f"https://www.bing.com/search?q={encoded}&form=QBRE"
    call(
        "http.request",
        "GET",
        "https://www.bing.com/",
        headers=headers,
        timeout=timeout,
        session="bing",
    )
    resp = call(
        "http.request",
        "GET",
        search_url,
        headers=headers,
        timeout=timeout,
        session="bing",
    )
    _http_raises(provider, resp, what="搜索请求")
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("li.b_algo")
    if not items:
        raise EngineFailure(provider, "无搜索结果")

    results: list[Result] = []
    for li in items[:count]:
        a = li.select_one("h2 a")
        if a is None:
            continue
        title = a.get_text(" ", strip=True)
        href = a.get("href", "")
        url = _decode_bing_redirect(href) or href
        p = li.select_one("p")
        snippet = _clean_snippet(p.get_text(" ", strip=True)) if p else ""
        results.append(Result(url=url, title=title, content=snippet))
    if not results:
        raise EngineFailure(provider, "无有效搜索结果")
    return results


# ── Tavily（keyed / keyless 自动选择） ─────────────────────


def tavily_search(query: str, *, count: int, timeout: float) -> list[Result]:
    """Tavily 搜索：有 `TAVILY_API_KEY` 走带 key 请求，没有则试 keyless 免费通道。

    keyless 模式声明 `X-Tavily-Access-Mode: keyless` 头；被服务端拒绝（4xx）
    仍以 EngineFailure 交层上，由壳层决定换引擎兜底。
    """
    provider = "tavily"
    key = os.environ.get("TAVILY_API_KEY", "")
    headers = {"Content-Type": "application/json"}
    if key:
        payload: dict[str, object] = {"api_key": key, "query": query}
    else:
        headers[_TAVILY_KEYLESS_HEADER] = "keyless"
        payload = {"query": query}
    payload["max_results"] = count
    payload["include_answer"] = False
    resp = call(
        "http.request",
        "POST",
        _TAVILY_URL,
        headers=headers,
        body=json.dumps(payload, ensure_ascii=False),
        timeout=timeout,
    )
    _http_raises(provider, resp, what="搜索请求")
    data = json.loads(resp.text)
    items = data.get("results") or []

    results: list[Result] = []
    for item in items:
        url = str(item.get("url", ""))
        title = str(item.get("title", ""))
        content = _clean_snippet(str(item.get("content", "")), search_config.snippet_max_len)
        published = str(item.get("publishedDate") or "")
        results.append(Result(url=url, title=title, content=content, published=published))
    if not results:
        raise EngineFailure(provider, "无搜索结果")
    return results


# ── Exa（经第二程 mcp 模块接 mcp.exa.ai，免 key） ──────────


_EXA_ENTRY_RE = re.compile(r"\[([^\[\]]+?)\]\((https?://[^\s)]+)\)")


def exa_search(query: str, *, count: int, timeout: float) -> list[Result]:
    """Exa 搜索：server 已连接（base.exa_available 门控过）后经 `mcp.call_tool` 执行。

    mcp.exa.ai 的回包是 markdown 文本（`[标题](url)` 形式）；逐条正则解析，
    提不出链接就整条降级为纯文本 Result（不能 web_open 点开但内容仍在）。
    """
    provider = "exa"
    try:
        text: object = call(
            "mcp.call_tool",
            EXA_MCP_SERVER,
            EXA_TOOL_NAME,
            {"query": query, "numResults": count},
        )
    except Exception as exc:
        raise EngineFailure(provider, str(exc) or type(exc).__name__) from exc
    if not isinstance(text, str) or not text.strip():
        raise EngineFailure(provider, "mcp 调用无输出")

    results: list[Result] = []
    lines = text.strip().splitlines()
    matches = [(m.group(1), m.group(2)) for m in _EXA_ENTRY_RE.finditer(text)]
    if not matches:
        # 全文无链接：整块当一条纯文本结果给出（web_open 点不了，但内容可用）
        return [Result(title=f"{provider}（无链接）", content=_clean_snippet(text))]

    for title, url in matches:
        # 摘要段：命中该链接那行、链接之后到行尾的文本（Exa 回包是「标题+链接+摘要」单行）
        snippet = ""
        for piece in lines:
            if url in piece:
                snippet = _clean_snippet(piece.split(url, 1)[1].lstrip(" –-—:"))
                break
        results.append(Result(url=url, title=title, content=snippet))
    logger.debug(f"exa 引擎返回 {len(results)} 条结果（经 mcp）")
    return results


__all__ = [
    "BING_UA",
    "EngineFailure",
    "Result",
    "bing_search",
    "exa_search",
    "tavily_search",
]
