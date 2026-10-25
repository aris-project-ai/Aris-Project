# MCP 模块契约（`src/aris/mcp/`）

> 通用 MCP 客户端：一个客户端接所有 server，官方 `mcp` SDK + 配置驱动 transport。
> 形状调研自 AstrBot / deepseek-harness / opencode——三家都是「一个通用客户端 +
> 配置驱动 transport」，不为单个端点手写适配。

## 定位

- 给 Aris 接入任意外部工具面（Exa 搜索、文件系统、数据库……任何 MCP server），
  汇入 agent 工具注册表；**第三程联网搜索**（Bing / Tavily / Exa 引擎池）的
  MCP 型端点（`mcp.exa.ai`）经本模块接入，不再手写 mini 适配。
- **不认识业务**：只搬运 SDK 与 server 之间的协议；工具 schema / 文案原样来自
  远端 server（AGENTS.md §6：工具文案不拟人化，唯一例外是 HTTP 报错的人话映射）。

## 总线面（同步服务）

| 服务 | 语义 |
|---|---|
| `mcp.ai_tools` | agent 工具声明（`.ai_tools` 契约，`list[ToolSpec]`）；**触发**连接 + 目录拉取。失败的 server 不连坐：缺席本轮声明，状态进 `mcp.status` |
| `tools.sync_generation(specs, owner)` | 不属于本模块——behavior 注册表提供的**世代同步**服务（旧代全量卸下 ↔ 新代全量登记，新代校验失败保旧代）。MCP 工具列表会动态变，靠它换装 |
| `mcp.call_tool(server, tool, arguments)` | 执行一次调用；同模块内部直调（fn 闭包），走总线仅供外部手动调用 |
| `mcp.status` | 状态快照（各 server 的 status / detail / tool 数），serve 探针与将来 WebUI 工具页用 |

事件：`mcp.tools_changed`——目录防抖重拉并世代换装完成后 emit（payload：`owner` / `count`）。

## 架构要点

- **owner 线程**：SDK 是 asyncio、Aris 总线是同步——SDK 跑在专属 daemon 线程的
  事件循环（AstrBot owner-task 模式搬线程），对外全部经
  `asyncio.run_coroutine_threadsafe` + Future 同步等待，超时给 `MCPToolError` 人话。
- **transport**：`config/mcp.toml` 驱动（stdio：`command`+`args`，子进程继承环境、
  `env_names` 声明凭据变量名；http：`url` + 可选 `bearer_env` 做 Bearer 头）。
- **工具汇入**：命名 `mcp_<server>_<tool>`（server 名约束 `[a-z0-9_-]{1,32}`，
  前缀化保证永不与内置 / 技能 / 业务工具撞名）；单工具 schema 非法只丢该工具
  （opencode 经验），不影响同 server 其他工具。
- **动态目录**：`tools/list_changed` → 防抖（`resync_debounce`）→ 重拉目录 →
  世代同步 → `emit("mcp.tools_changed")`。同步范围是 owner=mcp 的**全量**
  （server 断线即把它的工具从整代撤下）。
- **可靠性**：超时三分（`startup_timeout` 连接+initialize / `catalog_timeout`
  list_tools / `execution_timeout` call_tool）；断线指数退避
  （`backoff_base` → `backoff_max`，连接保持满 `backoff_reset` 重置预算）；
  连续失败超过 6 次状态进「已失败」（**仍会重试**，不把 server 钉死——dsh 的
  激进停摆模式在这里被认为有害）。
- **结果归一化**：text 直接拼；image / audio 媒体落盘 `data/mcp/media/` 换成
  说明文字（Aris 是文字/语音期）；`content` 空而 `structuredContent` 有值时
  stringify 兜底（dsh 的已知缺陷反向修）；`isError` 加 `[工具返回错误标识]` 前缀。

## 配置（`config/mcp.toml`）

server 表 `[servers.<name>]` + 三组超时 + 退避参数，缺文件 = 未接任何 server
（模块零开销，`.ai_tools` 返回空）。密钥只写环境变量名，值进 `.env`。

## 边界（明确不做）

- server 配置热重载（改 toml 要重启进程）；
- 每工具粒度的开关（`registry` 的 `enabled` 契约已备，等 WebUI 工具页再收）；
- OAuth 授权流（http server 只拿起始 Bearer）。
