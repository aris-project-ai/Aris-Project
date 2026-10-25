# behavior 重整与工具注册改造（施工文档，暂存）

> **这是临时施工文档**：三程做完后整体删除本文件，不留存档。
> 决策起因：knowledge 的 agent 工具壳（schema / 返回格式 / 降级文案）塞在
> `behavior/tools/` 里，违反「能力归属模块」与 CMCB 边界；同时 WebUI 路线图
> 里有「工具页：列已有工具 / 简介 / 开关 / 失败醒目展示」，工具注册需要为它打地基。
> 讨论时间：2026-10-25，开发者（莫琳）逐项定案。

## 0. 路线（开发者定案的三程顺序）

| 程 | 内容 | 状态 |
|---|---|---|
| 1 | **工具表注册与现有工具迁移**（本文件第 1 节） | ✅ 已并入 develop（b1e98c4） |
| 2 | **通用 MCP 模块**（第 2 节；契约文档 `MCP.md`） | ✅ 已并入 develop（本次） |
| 3 | **联网搜索重整**（第 3 节，草案方向） | 待开工 |

顺序含义：Exa 引擎等 MCP 型端点**不再写 mini 适配**，直接等第 2 程的通用 MCP
模块，之后第 3 程的搜索引擎池（Bing / Tavily+keyless / Exa）借它接入。

## 1. 第一程：工具表注册与现有工具迁移

### 1.1 已定案的设计

- **契约载体 `core/tools.py: ToolSpec`**（frozen dataclass）：
  `name / description / parameters / fn / owner / needs_context / enabled`。
  `enabled` 来自声明方的自身配置（如 knowledge 的 `enabled`）：照常声明进
  registry（CLI / WebUI 能看到它的存在与状态），但 `definitions()` 过滤掉
  disabled 的工具——**模型看不到，不占请求工具面**；执行侧 fn 仍保留
  「已关闭」降级文案（手动调用兜底）。这就是未来「工具开关」的地基。
- **重名策略**：warning 后后注册者胜（与 skills 覆盖语义一致）。
  放 core 不放 behavior：knowledge 声明工具要**运行期**构造它，放 behavior 会
  形成「业务模块 → agent 栈」的运行期 import（AGENTS §6「纯类型引用」豁免盖不住）；
  core 是共享词汇层，`ToolDefinition` 已有先例住在 core。
- **声明契约 `<模块名>.ai_tools`**：模块在自家 `__init__` 里
  `provide("<模块>.ai_tools", fn)`，fn 无参调用返回 `list[ToolSpec]`。
  发现方式：behavior 装配时遍历 `bus.services()` 按 `.ai_tools` 后缀探询
  （behavior 认契约不认识模块；新模块接 agent 面 = 自家 tools.py + 一行 provide，
  behavior / serve / assembly 零改动）。
- **工具的 fn 本身不上总线**：总线只传声明；执行体由 registry 收编持有，
  agent loop 经 `tools.execute` 执行。同模块内部调用不走总线
  （AGENTS §6 边界），故 knowledge 壳内直调 `get_service().search()`。
- **registry 变化**：
  - `RegisteredTool` 增加 `owner: str`（提供方模块名，工具页展示 / 开关用）；
  - 新增 `register_spec(spec)` 与模块级 `register_declared_tools(registry)`；
  - 重名注册不再静默覆盖，改记 warning；
  - **持久失败清单** `registry.declaration_failures: list[tuple[provider, error]]`：
    探询失败（服务抛错 / 返回 None / 畸形 spec）逐条收进去并记 warning，
    日志是时间线，WebUI 工具页将来把「声明了但没装上」的条目醒目置顶。
- **文案基调**：工具文案不做人味。Bing 直连的意义是给 AI 真实的浏览器体验，
  浏览器不会拟人化返回；只有 429 这类 HTTP 报错给映射成「限流 / 需要鉴权」等人话。
  第一人称口吻感不进工具层（拟人语气归 prompt 层）。
- **推荐被否的备选**：总线自动注册（模块 import 时 `call("tools.register")` /
  订阅 ready 事件）——时序魔法 + 总线宽容降级会静默丢工具；做成 skill——
  激活制与「Aris 自主随时调」冲突，KNOWLEDGE-BASE.md 定案也说知识库不做 skill。

### 1.2 改动清单（本程验收点）

| 位置 | 动作 |
|---|---|
| `core/tools.py` | 新增：`ToolSpec` + `ToolFn`（简短契约说明） |
| `behavior/registry.py` | `register_spec` / `register_declared_tools` / `owner` / 重名 warning / 失败清单 |
| `behavior/runtime.py` | 内置 → 技能 → 声明探询的装配顺序；`tool_count()` 统计**全部登记**（含 disabled），探针数字稳定 |
| `cli.py` | 新增 `aris tools list`（name / owner / enabled / description 截断）与 `aris services list`（总线服务清单）；不碰 WebUI |
| `behavior/tools/knowledge_search.py` | 删除 |
| `knowledge/tools.py` | 新增：壳整体迁入；`tool_specs()` 导出；同模块直调 service |
| `knowledge/__init__.py` | `provide("knowledge.ai_tools", tool_specs)` + docstring 纠偏 |
| 测试 | 迁移两个旧测试的 import；新增探询用例（fake `.ai_tools` / 畸形 spec / 重名 warning / 失败清单） |
| 文档 | `AGENTS.md` §6「新的 agent 工具」拆两条；`CMCB.md` 服务表 + 契约说明；`KNOWLEDGE-BASE.md` 工具路径改 `knowledge/tools.py` |

验收：`bash scripts/check.sh` 全绿；工具名 / schema / 返回 JSON 结构不变
（模型侧零感知）；工具数不变（探询把 knowledge 工具收编回来仍是 5 个）；工具
失败仍宽容降级不抛 UI。

## 2. 第二程：通用 MCP 模块（草案，开工前先重读本节核对现状）

调研结论（2026-10-25，参考仓在 `data/temp/`：AstrBot / deepseek-harness / opencode）：

- **通用客户端不是每家写适配**：三家都把 MCP 收敛成一个客户端 + 配置驱动的
  transport（stdio / streamable-http）。Python 侧用官方 `mcp` SDK，一个模块
  接所有 server；手写的只有 transport 这类极少数件。
- **async 边界**：官方 SDK 是 asyncio；Aris 总线是同步。方案 = SDK 跑在
  **专属 asyncio owner 线程**（AstrBot owner-task 模式搬线程），只暴露**同步**
  总线服务 `mcp.list_tools / call_tool / status`，事件 `mcp.tools_changed`。
- **配置**：`config/mcp.toml`（server 名即命名空间，约束 `[a-z0-9_-]{1,32}`；
  stdio 补命令白名单与 env 凭据清洗；密钥仍只进 `.env`）。
- **工具汇入**：工具列表是动态的 → 走第一程预留的**世代同步语义**
  （两相式：旧代全量 unregister ↔ 新代全量注册，失败保旧代；dsh 验证过的模式），
  命名 `mcp_<server>_<tool>`，server 名约束防撞；单工具 schema 校验失败只丢该
  工具不连坐（opencode）。
- **可靠性**：超时三分（startup / catalog / execution）+ 断线指数退避
  （500ms→30s、稳定期重置预算、耗尽进失败清单）；`tools/list_changed` → 防抖后
  代际重同步 + `emit("mcp.tools_changed")`。
- **结果归一化**：text 直接给；image 等媒体先记文件落盘 + 说明文字（Aris 是
  文字 / 语音期）；`content` 空而 `structuredContent` 有值时 stringify 兜底
  （dsh 的已知缺陷反向修）；HTTP 报错人话映射沿用第一程基调。

## 3. 第三程：联网搜索重整（草案）

- **引擎池定案**：Bing 直连 + Tavily（含 **keyless 兜底** `X-Tavily-Access-Mode:
  keyless`）+ **Exa**（经第 2 程 MCP 模块接 `mcp.exa.ai`，免 key）。
- **引擎注册表结构化**：引擎模块只吐归一化 `Result`（`url / title? / content? /
  time.published?`，抄 opencode schema 形状），壳层统一渲染 markdown；
  失败的 `ToolFailure` metadata 带 `provider`（模型与 WebUI 都知道谁出的错）。
- **429 冷却**：解析 `retry-after`，冷却中跳过引擎；`attempted` 集合防回环
  （抄 opencode，去掉多 KV/多会话亲和——我们没有那套状态设施）。
- **不改动的**：`web_open` 还是走引擎 id → 抓正文的老约定（会话级缓存问题等
  会话上下文重构时一起治）；HTTP 错误人话映射沿用第 1 程基调。
- **不碰的**：不做 provider 持久化选型 / 用户授权 UI（无对应设施）；不做插件系统。

## 4. 调研材料指针

- `data/temp/opencode/`（sst/opencode）：`websearch.ts`（领域服务 + 冷却 +
  Selection）、`plugin/websearch/*.ts`（六引擎）、`tool/plugin/websearch.ts`、
  `mcp/`（client.ts / index.ts / stdio.ts）、`tool/mcp.ts`。
- `data/temp/AstrBot/`（Python）：`astrbot/core/agent/mcp_client.py`、
  `astrbot/core/provider/func_tool_manager.py`（owner-task / SDK 用法）。
- `data/temp/deepseek-harness/`（Node）：`packages/mcp/mcp-client/`（退避 /
  世代同步 / 命名哈希），个别「structuredContent 不可见」讨论是它的现状缺陷。
- 以上参考仓只读，什么都不改；三程完成、本文件删除后，「`.ai_tools` 契约」等
  长期规则留在 `AGENTS.md` §6 与 `CMCB.md`，不留过程文档。
