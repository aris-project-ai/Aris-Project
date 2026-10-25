"""mcp 模块的可调参数（优先级：代码内默认值 < `config/mcp.toml`）。

server 配置是**结构化嵌套表**（`[servers.<名>]`），与普通扁平字段混在同一个
toml：`load_config` 会把 `servers` 整表读进 dataclass 字段，再在这里规范化
（名字校验 / 字段校验 / 非法条目丢弃记 warning，宽容降级）。

命名约束（`config/mcp.toml` 里的 `[servers.<name>]`）：`[a-z0-9_-]{1,32}`。
server 名会进入工具名（`mcp_<server>_<tool>`），约束是为了防撞、防注入
（AGENTS.md §6：调用方拿到 `None` 不能直接属性访问，这里同样在源头拒绝脏名字）。

密钥不进 toml：stdio 服务试进程环境变量名（`env_names`）与 http 鉴权头
（`bearer_env`）都只写**环境变量名**，值从 `.env`（已 setdefault 进
`os.environ`）取。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from loguru import logger

from ..cfgtoml import load_config

# server 名合法字符：小写字母 / 数字 / 下划线 / 连字符，1..32
_NAME_RE = re.compile(r"^[a-z0-9_-]{1,32}$")

# 支持的 transport（收口原则：枚举 = 代码内常量，不进 toml 校验文案）
TRANSPORTS = ("stdio", "http")


@dataclass
class McpServerConfig:
    """一个 MCP server 的接入配置（`config/mcp.toml` 的 `[servers.<name>]`）。

    stdio：`command` + `args` 启动子进程（`env_names` 转发 `.env` 里的凭据）；
    http：`url` 指向 MCP streamable-http 端点（`bearer_env` 可选，做 Bearer 头）。
    """

    transport: str = "stdio"
    # stdio 专用
    command: str = ""
    args: list[str] = field(default_factory=list)
    # 环境变量名列表：把这些 `.env` / 环境变量原样转发给子进程（只名字，不写值）
    env_names: list[str] = field(default_factory=list)
    # http 专用
    url: str = ""
    # Bearer token 的环境变量名（None = 不带鉴权头）
    bearer_env: str | None = None


@dataclass
class McpConfig:
    """mcp 模块配置（三组超时 + 退避 + server 表）。"""

    # server 表：name -> 配置（toml 原始 dict，get_mcp_config 里规范化）
    servers: dict = field(default_factory=dict)
    # 启动超时：连接 + initialize 单 server 上限（秒）
    startup_timeout: float = 30.0
    # 目录超时：list_tools 单次上限（秒）
    catalog_timeout: float = 30.0
    # 执行超时：call_tool 一次上限（秒）
    execution_timeout: float = 180.0
    # 断线退避：首次等待（秒）
    backoff_base: float = 0.5
    # 断线退避：上限（秒）
    backoff_max: float = 30.0
    # 稳定期：连接保持多久（秒）后重置连续失败预算
    backoff_reset: float = 300.0
    # `tools/list_changed` 防抖窗口（秒）
    resync_debounce: float = 1.0


def _normalize(raw: object, *, where: str) -> dict[str, McpServerConfig]:
    """把 toml 读来的 server 表规范化；非法条目丢弃并记 warning（宽容降级）。"""
    servers: dict[str, McpServerConfig] = {}
    if not isinstance(raw, dict):
        return servers
    for name, item in raw.items():
        where_name = f"{where}.{name}"
        if not isinstance(name, str) or not _NAME_RE.match(name):
            logger.warning(f"mcp 配置：{where_name} 的名字不合法（需 {_NAME_RE.pattern}），已丢弃")
            continue
        if not isinstance(item, dict):
            logger.warning(f"mcp 配置：{where_name} 不是表，已丢弃")
            continue
        cfg = McpServerConfig(
            transport=str(item.get("transport", "stdio")),
            command=str(item.get("command", "")),
            args=[str(a) for a in (item.get("args") or [])],
            env_names=[str(n) for n in (item.get("env_names") or [])],
            url=str(item.get("url", "")),
            bearer_env=str(item["bearer_env"]) if item.get("bearer_env") else None,
        )
        if cfg.transport not in TRANSPORTS:
            logger.warning(f"mcp 配置：{where_name} transport={cfg.transport} 不支持，已忽略")
            continue
        if cfg.transport == "stdio" and not cfg.command:
            logger.warning(f"mcp 配置：{where_name} 是 stdio 但未给 command，已忽略")
            continue
        if cfg.transport == "http" and not cfg.url:
            logger.warning(f"mcp 配置：{where_name} 是 http 但未给 url，已忽略")
            continue
        servers[name] = cfg
    return servers


@lru_cache
def get_mcp_config() -> McpConfig:
    """加载 mcp 配置单例（server 表在此时规范化，非法条目已丢弃）。"""
    cfg = load_config(McpConfig(), "mcp.toml")
    cfg.servers = _normalize(cfg.servers, where="servers")
    return cfg
