"""进程级装配：LLM engine + behavior 运行时（v1.0 M1 上收）。

为什么放组装根：`tools.execute` / `loop.run` / `skills.menu` / 引擎的
`llm.deltas` 都是**单槽**总线服务，原来由每个 `ChatSession` 构造时自建并
`provide`，多开一段对话就覆盖一遍（多人格 D1/D2 下必然互相顶掉）。
上收后一个进程只有一份；`aris serve` / `aris web` / `aris chat` 三条入口
都经 :func:`get_runtime` 取，构建幂等（重复调用返回同一份）。
"""

from __future__ import annotations

from loguru import logger

from ..behavior import BehaviorRuntime
from ..config import get_settings
from ..core.llm import LLMEngine, load_providers

# 进程级唯一运行时（None = 尚未装配）
_runtime: BehaviorRuntime | None = None


def build_engine() -> LLMEngine:
    """按 `.env` + `config/providers.toml` 建 LLM engine。"""
    settings = get_settings()
    providers = load_providers(settings.llm_providers_file)
    return LLMEngine(
        providers,
        timeout=settings.llm_fallback_timeout,
        first_token_stall=settings.llm_first_token_stall,
        error_message=settings.llm_error_message,
    )


def get_runtime(*, rebuild: bool = False) -> BehaviorRuntime:
    """取进程级 behavior 运行时；首次调用时构建，之后幂等返回同一份。"""
    global _runtime
    if _runtime is None or rebuild:
        _runtime = BehaviorRuntime(build_engine())
        logger.debug(f"behavior 运行时已装配：{_runtime.tool_count()} 个工具")
    return _runtime


def peek_runtime() -> BehaviorRuntime | None:
    """看已装配的运行时（None = 还没建）；供探针用，不触发构建。"""
    return _runtime


def reset_runtime() -> None:
    """丢弃已装配的运行时（测试用；不注销已注册的总线服务）。"""
    global _runtime
    _runtime = None


__all__ = ["build_engine", "get_runtime", "peek_runtime", "reset_runtime"]
