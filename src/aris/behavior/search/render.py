"""搜索共用渲染层：归一化 Result → markdown + id→url 收档。

`tools/web_search.py`（模型可见壳）与 `web_open` 共用：引擎只吐 `Result`，
这里统一渲染 markdown（外层 JSON 标识在壳层包，此处只出内部文本）；
`RECENT_RESULTS`（id → title/url）是 web_open 的点开依据（覆盖式缓存，
进程级最近一次搜索）。
"""

from __future__ import annotations

from .base import Result

# 最近一次搜索的 id → {title, url}，供 web_open 按 id 点开（web_search 壳层写、web_open 读）
RECENT_RESULTS: dict[int, dict[str, str]] = {}


def render_results(results: list[Result]) -> str:
    """渲染结果列表为 markdown（每条带自增 id；无链接条目不收档）。"""
    RECENT_RESULTS.clear()
    lines: list[str] = []
    for idx, item in enumerate(results, start=1):
        if item.url:
            title = item.title or item.url
            lines.append(f"{idx}. [{title}]({item.url})")
            RECENT_RESULTS[idx] = {"title": item.title, "url": item.url}
        else:
            lines.append(f"{idx}. {item.title or '（无链接结果）'}")
        if item.content:
            lines.append(f"   {item.content}")
        if item.published:
            lines.append(f"   （发布时间：{item.published}）")
    return "\n".join(lines)


__all__ = ["RECENT_RESULTS", "render_results"]
