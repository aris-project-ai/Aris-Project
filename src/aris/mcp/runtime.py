"""mcp 模块的运行时：通用 MCP 客户端（owner 线程 asyncio + 同步总线服务）。

设计定案（docs/forAiDoc/BEHAVIOR-REWORK.md 第 2 节）：

- 官方 ``mcp`` SDK（v2）是 asyncio，Aris 总线是同步——SDK 跑在**专属 owner
  线程**的事件循环里，对外只给同步入口（AstrBot owner-task 模式搬线程）：
  `catalog_specs` / `call_tool_sync` / `status_snapshot`；
- 一个客户端接所有 server：transport 由 `config/mcp.toml` 驱动（stdio / http），
  不为单个 MCP 端点写适配；
- 工具列表动态：`tools/list_changed` → 防抖 → 重拉目录 → 经总线服务
  ``tools.sync_generation`` 做「旧代↔新代」两相式换装 → ``emit("mcp.tools_changed")``；
- 断线：指数退避（backoff_base → backoff_max），连接保持满稳定期重置预算；
  连续失败超过预算状态 进「已失败」但仍会重试——一次网络抖动不把 server 钉死。

知道但刻意不做的：server 配置热重载（改 toml 要重启）、多路并发洪泛控制。
"""

from __future__ import annotations

import asyncio
import atexit
import base64
import contextlib
import json
import os
import threading
import time
from concurrent.futures import Future
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import mcp.types as mcp_types
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from ..core import call, emit
from .conf import McpConfig, McpServerConfig

# 连续失败超过该次数后状态进「已失败」（超过后仍按上限间隔重试，不钉死 server）
DEFAULT_MAX_CONSECUTIVE_FAILURES = 6


class MCPToolError(RuntimeError):
    """MCP 调用失败（human text：交给模型 / 注册表层，不裸抛 traceback）。"""


class _ServerState:
    """一个 server 的连接态：状态面字段跨线程读，会话字段只 owner 线程摸。"""

    def __init__(self, name: str, cfg: McpServerConfig) -> None:
        self.name = name
        self.cfg = cfg
        # 状态面（跨线程，只读语义：字符串原子）
        self.status = "未连接"
        self.detail: str | None = None
        self.tool_count = 0
        # owner 线程内部
        self.session: ClientSession | None = None
        self.tools: dict[str, mcp_types.Tool] = {}  # 最近一次成功目录
        self.catalog_stale = False  # tools/list_changed 之后待重拉
        # 事件（owner loop 上下文创建）
        self.connected: asyncio.Event
        self.reconnect: asyncio.Event

    def arm(self) -> None:
        """在 owner loop 里创建事件对象（跨线程拿到的 Event 必须属于同一 loop）。"""
        self.connected = asyncio.Event()
        self.reconnect = asyncio.Event()


class McpRuntime:
    """通用 MCP 客户端运行时：一个 owner 线程 + 配置驱动的全部 server。"""

    def __init__(self, config: McpConfig, data_dir: Path) -> None:
        self._config = config
        self._data_dir = data_dir
        self._media_dir = data_dir / "mcp" / "media"
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._start_guard = threading.Lock()
        self._states: dict[str, _ServerState] = {
            name: _ServerState(name, cfg) for name, cfg in config.servers.items()
        }
        self._resync_task: asyncio.Task | None = None
        self._resync_guard = threading.Lock()
        # 进程退出时尽量收掉子进程（daemon 线程不做兜底会漏 stdio server）
        atexit.register(self.stop)

    # ---------- 线程 / 提交 ----------

    def _ensure_started(self) -> None:
        """懒启动 owner 线程（幂等；没有 server 也照起——call/status 都要问它）。"""
        if self._thread is not None and self._thread.is_alive():
            return
        with self._start_guard:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._owner_thread, name="aris-mcp-owner", daemon=True
            )
            self._thread.start()
            if not self._ready.wait(timeout=self._config.startup_timeout):
                raise MCPToolError("mcp owner 线程未能在启动超时内就绪")

    def _owner_thread(self) -> None:
        """owner 线程入口：独占一份事件循环，长期 run。"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._boot())
        except Exception as exc:  # noqa: BLE001 —— 启动失败要有痕迹，线程本身退出
            logger.error(f"mcp owner 线程启动异常：{exc}")
        self._ready.set()
        try:
            loop.run_forever()
        except Exception as exc:  # noqa: BLE001 —— 线程整体坏了要有痕迹
            logger.error(f"mcp owner 线程异常退出：{exc}")
        finally:
            loop.close()

    async def _boot(self) -> None:
        """建状态、拉起每个 server 的维护协程。"""
        for st in self._states.values():
            st.arm()
            self._loop.create_task(self._maintain(st.name), name=f"mcp-maintain-{st.name}")

    def _submit(self, coro: Any, *, timeout: float) -> Any:
        """把协程交给 owner loop 同步等待结果（超时即报 MCPToolError）。"""
        self._ensure_started()
        assert self._loop is not None
        future: Future[Any] = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=timeout)
        except TimeoutError as exc:
            future.cancel()
            raise MCPToolError(f"mcp 操作超时（{timeout:.0f}s）") from exc

    # ---------- server 维护 ----------

    async def _maintain(self, name: str) -> None:
        """单个 server 的长命循环：连上 → 刷目录 → 等断线标志 → 按退避重连。"""
        st = self._states[name]
        backoff = self._config.backoff_base
        fails = 0
        while True:
            st.reconnect.clear()
            st.connected.clear()
            connected_at: float | None = None
            try:
                async with AsyncExitStack() as stack:
                    session = await self._open(name, st, stack)
                    st.session = session
                    st.detail = None
                    # 目录刷新（catalog_timeout）；失败同走重连路径
                    result = await asyncio.wait_for(
                        session.list_tools(), self._config.catalog_timeout
                    )
                    st.tools = {tool.name: tool for tool in result.tools}
                    st.catalog_stale = False
                    st.tool_count = len(st.tools)
                    st.status = "已连接"
                    st.connected.set()
                    connected_at = time.monotonic()
                    logger.info(f"mcp: {name} 已连接（{len(st.tools)} 个工具）")
                    # 首次连上后立刻把工具面同步进注册表（世代换装）
                    self._schedule_resync()
                    # 待在这里直到外部要求重连 / 断线
                    await st.reconnect.wait()
            except asyncio.CancelledError:
                return
            except Exception as exc:  # noqa: BLE001 —— 任何连接/目录失败都走退避重连
                st.session = None
                if connected_at is not None and (
                    time.monotonic() - connected_at >= self._config.backoff_reset
                ):
                    fails = 0  # 稳定期重置预算
                fails += 1
                human = _humanize(exc)
                st.detail = human
                if fails >= DEFAULT_MAX_CONSECUTIVE_FAILURES:
                    st.status = "已失败"
                else:
                    st.status = "重连中"
                logger.warning(f"mcp: {name} {st.status}（{human}）；{backoff:.1f}s 后重试")
                # 断线要立刻把它的工具从注册表撤下（世代换装，drop 该 server）
                self._schedule_resync()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._config.backoff_max)
                continue
            # 正常走到这 = reconnect 标志（调用失败 / list_changed 断线要求）
            st.session = None
            if not fails and backoff != self._config.backoff_base:
                backoff = self._config.backoff_base

    async def _open(self, name: str, st: _ServerState, stack: AsyncExitStack) -> ClientSession:
        """按 transport 建 client + session（startup_timeout 兜底）。"""
        cfg = st.cfg
        if cfg.transport == "stdio":
            # 子进程继承当前环境（.env 已被 config 层 setdefault 进 os.environ，
            # env_names 声明的凭据因而在内）；显式再拷一份避免被 SDK 的安全默认裁掉
            env = dict(os.environ)
            env.update({key: os.environ[key] for key in cfg.env_names if key in os.environ})
            params = StdioServerParameters(command=cfg.command, args=list(cfg.args), env=env)
            read, write = await stack.enter_async_context(stdio_client(params))
        else:
            headers = None
            if cfg.bearer_env:
                token = os.environ.get(cfg.bearer_env)
                if not token:
                    raise MCPToolError(
                        f"mcp: {name} 的鉴权环境变量 {cfg.bearer_env} 未设置（写进 .env）"
                    )
                headers = {"Authorization": f"Bearer {token}"}
            http_client = create_mcp_http_client(headers=headers)
            read, write, _sid = await stack.enter_async_context(
                streamable_http_client(cfg.url, http_client=http_client)
            )
        session = await stack.enter_async_context(
            ClientSession(
                read,
                write,
                read_timeout_seconds=self._config.catalog_timeout,
                message_handler=self._handler(name),
            )
        )
        await asyncio.wait_for(session.initialize(), self._config.startup_timeout)
        return session

    def _handler(self, name: str) -> Any:
        """client message handler：断线 → 要求重连；目录变更 → 防抖重拉目录。"""

        async def _on_message(message: Any) -> None:
            st = self._states.get(name)
            if st is None:
                return
            if isinstance(message, Exception):
                logger.warning(f"mcp: {name} 传输异常：{message}")
                st.reconnect.set()
                return
            if isinstance(message, mcp_types.ToolListChangedNotification):
                st.catalog_stale = True
                self._schedule_resync()

        return _on_message

    # ---------- 目录同步（世代换装） ----------

    def _schedule_resync(self) -> None:
        """防抖排一个世代同步（owner loop 上下文调用）。"""
        assert self._loop is not None
        loop = self._loop

        async def _worker() -> None:
            try:
                deadline = loop.time() + self._config.resync_debounce
                while True:
                    now = loop.time()
                    if now >= deadline:
                        break
                    await asyncio.sleep(deadline - now)
                self._resync_task = None
                await self._resync()
            except asyncio.CancelledError:
                return

        with self._resync_guard:
            if self._resync_task is not None and not self._resync_task.done():
                return  # 已有在途的防抖任务，它醒来时自然会带上这次的变更
            self._resync_task = loop.create_task(_worker(), name="mcp-resync")

    async def _resync(self) -> None:
        """全量世代同步：把「当前还连着的全部 server」的目录换装进注册表。

        同步范围是 owner=mcp 的**全量**（不按 server 细分世代）——某个 server 断线
        会把它的工具从整代里撤掉。单一工具 schema 非法只丢该工具（opencode 经验）。
        """
        specs: list = []
        for name, st in self._states.items():
            if st.status != "已连接":
                continue
            if st.catalog_stale and st.session is not None:
                try:
                    result = await asyncio.wait_for(
                        st.session.list_tools(), self._config.catalog_timeout
                    )
                except Exception as exc:  # noqa: BLE001 —— 目录重拉失败不连坐
                    logger.warning(f"mcp: {name} 目录重拉失败：{_humanize(exc)}")
                    continue
                st.tools = {tool.name: tool for tool in result.tools}
                st.tool_count = len(st.tools)
                st.catalog_stale = False
            specs.extend(self._specs_of(name, st))
        if not specs and not any(st.status == "已连接" for st in self._states.values()):
            try:
                call("tools.sync_generation", specs=[], owner="mcp")
            except Exception as exc:  # noqa: BLE001 —— 服务没起/没变化都只是状态问题
                logger.debug(f"mcp: 世代同步跳过（{exc}）")
            return
        try:
            outcome = call("tools.sync_generation", specs=specs, owner="mcp")
        except Exception as exc:  # noqa: BLE001 —— behavior 未装配时保旧代
            logger.warning(f"mcp: 世代同步失败，注册表保持旧代：{_humanize(exc)}")
            return
        registered = (outcome or {}).get("registered", len(specs))
        emit("mcp.tools_changed", {"owner": "mcp", "count": registered})
        logger.debug(f"mcp: 世代同步完成（{registered} 个工具）")

    def _specs_of(self, name: str, st: _ServerState) -> list[Any]:
        """把一个 server 的目录转成 ToolSpec 声明；单工具失败只丢该工具。"""
        from .tools import spec_from_tool

        def runner(tool_name: str, args: dict) -> str:
            # spec_from_tool 的约定签名：(tool_name, arguments) -> 文本
            return self.call_tool_sync(st.name, tool_name, args)

        specs = []
        for tool_name, tool in (st.tools or {}).items():
            try:
                specs.append(spec_from_tool(st.name, tool, runner))
            except Exception as exc:  # noqa: BLE001 —— schema 非法只丢该工具
                logger.warning(f"mcp: {name} 的工具 {tool_name} 声明非法，已丢弃：{exc}")
        return specs

    # ---------- 同步门面（owner 线程之外调用） ----------

    def catalog_specs(self) -> list[Any]:
        """同步取全部 server 的工具声明（触发连接；接线失败跳过不抛）。"""
        self._ensure_started()

        async def _gather() -> list[Any]:
            tasks = [
                asyncio.wait_for(st.connected.wait(), self._config.catalog_timeout)
                for st in self._states.values()
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            agg: list[Any] = []
            for st in self._states.values():
                agg.extend(self._specs_of(st.name, st))
            return agg

        total = self._config.startup_timeout + self._config.catalog_timeout + 5
        return self._submit(_gather(), timeout=total + 5)

    def call_tool_sync(self, server: str, tool: str, arguments: dict) -> str:
        """同步执行一次 MCP 工具调用，返回归一化文本（失败抛 MCPToolError）。"""
        self._ensure_started()

        async def _run() -> str:
            st = self._states.get(server)
            if st is None:
                raise MCPToolError(f"mcp: server {server} 未在 config/mcp.toml 配置")
            try:
                await asyncio.wait_for(st.connected.wait(), self._config.catalog_timeout)
            except TimeoutError as exc:
                raise MCPToolError(
                    f"mcp: server {server} 等待连接超时（{self._config.catalog_timeout:.0f}s）"
                ) from exc
            session = st.session
            if session is None:
                raise MCPToolError(f"mcp: server {server} 当前不可用（{st.status}）")
            try:
                result = await asyncio.wait_for(
                    session.call_tool(
                        tool,
                        arguments=arguments,
                        read_timeout_seconds=self._config.execution_timeout,
                    ),
                    self._config.execution_timeout + 5,
                )
            except TimeoutError as exc:
                st.reconnect.set()
                raise MCPToolError(
                    f"mcp 执行超时（{self._config.execution_timeout:.0f}s）：{server}.{tool}"
                ) from exc
            except Exception as exc:
                st.reconnect.set()
                raise MCPToolError(f"mcp 执行失败：{_humanize(exc)}") from exc
            return _normalize_result(result, self._media_dir)

        return self._submit(_run(), timeout=self._config.execution_timeout + 15)

    def status_snapshot(self) -> dict[str, Any]:
        """同步状态快照（只读：已配置 server 数 + 各 server 状态面）。"""
        servers = {
            name: {
                "status": st.status,
                "detail": st.detail,
                "tools": st.tool_count,
            }
            for name, st in self._states.items()
        }
        return {
            "configured": len(servers),
            "owner_alive": bool(self._thread and self._thread.is_alive()),
            "servers": servers,
        }

    def stop(self) -> None:
        """收尾：退出维护协程、关会话、停事件循环（幂等；进程退出时由 atexit 调）。"""
        thread, loop = self._thread, self._loop
        if thread is None or not thread.is_alive() or loop is None:
            return

        async def _shutdown() -> None:
            for st in self._states.values():
                st.reconnect.set()
                st.connected.set()

        with contextlib.suppress(Exception):
            asyncio.run_coroutine_threadsafe(_shutdown(), loop).result(timeout=5)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)


def _humanize(exc: Exception) -> str:
    """异常 → 人话（沿用第一程基调：HTTP 报错给限流 / 鉴权类可读词）。"""
    text = str(exc)
    lowered = text.lower()
    if "429" in text or "rate limit" in lowered or "too many requests" in lowered:
        return "上游限流（429），稍后再试"
    if "401" in text or "403" in text or "unauthorized" in lowered or "forbidden" in lowered:
        return "鉴权失败（401/403）——检查 bearer token / key"
    if "timed out" in lowered or "timeout" in lowered:
        return "连接或响应超时"
    return text or type(exc).__name__


def _normalize_result(result: mcp_types.CallToolResult, media_dir: Path) -> str:
    """CallToolResult → 给模型读的文本。

    text 直接拼；image / audio 媒体落盘（data/mcp/media）换成说明文字（Aris
    是文字 / 语音期）；content 空而 structured_content 有值时 stringify 兜底
    （dsh 的「structuredContent 不可见」缺陷反向修）。
    """
    parts: list[str] = []
    for block in result.content or []:
        if isinstance(block, mcp_types.TextContent):
            parts.append(block.text)
        elif isinstance(block, (mcp_types.ImageContent, mcp_types.AudioContent)):
            parts.append(_save_media(block, media_dir))
        elif isinstance(block, mcp_types.EmbeddedResource):
            resource = block.resource
            text = getattr(resource, "text", None)
            if text:
                parts.append(str(text))
            else:
                parts.append(f"[资源输出（{block.uri}）：非文本内容，此处略]")
        else:
            parts.append(f"[未识别的输出块：{type(block).__name__}，已省略]")
    text = "\n\n".join(p for p in parts if p)
    if not text and result.structured_content is not None:
        text = json.dumps(result.structured_content, ensure_ascii=False)
    if result.is_error:
        text = text or "(tool errored)"
        text = f"[工具返回错误标识]\n{text}"
    return text


def _save_media(block: Any, media_dir: Path) -> str:
    """媒体块落盘（幂等目录），返回给模型的说明文字（带路径）。"""
    media_dir.mkdir(parents=True, exist_ok=True)
    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "audio/wav": "wav",
        "audio/mpeg": "mp3",
    }
    mime = getattr(block, "mime_type", "") or "bin"
    ext = ext_map.get(mime, mime.rsplit("/", 1)[-1] or "bin")
    suffix = f"_{int(time.time() * 1000)}"
    path = media_dir / f"mcp-media{suffix}.{ext}"
    data = getattr(block, "data", "") or ""
    try:
        path.write_bytes(base64.b64decode(data))
    except Exception as exc:  # noqa: BLE001 —— 落盘失败只说明
        return f"[{type(block).__name__} 输出保存失败：{mime}] {_humanize(exc)}"
    kind = "音频" if mime.startswith("audio/") else "图片"
    return f"[{kind}输出已保存：{path}]（格式 {mime}; 当前是文字/语音期，仅保留文件）"


__all__ = [
    "DEFAULT_MAX_CONSECUTIVE_FAILURES",
    "MCPToolError",
    "McpRuntime",
    "_humanize",
]
