# 开发进度

> 每次开发前先读本文件，了解**当前**状态。
> 本文件只记当前进度（现状速览 / 最近动态 / 当前聚焦 / 路线）；已翻页的历史条目
> 原文归档在 `docs/developDoc/PROGRESS-ARCHIVE.md`（含各次踩坑记录，查旧事去那里）。

## 当前版本：v0.4.2（beta，2026-09-24）

## 现状速览

| 模块 | 状态 |
|---|---|
| `core/` | 完成：CMCB 总线（core 16 个服务，全项目 52 个注册点；含事件广播 + 审计）+ LLM 多提供方 / fallback / 流式 / 工具调用 |
| `behavior/` | 完成：agent loop、工具注册表、内置工具（`web_search` / `web_open` / `knowledge_search`）、skills 系统 |
| `chat/` | 完成：会话逻辑 + TUI（`aris chat`），定位开发调试 |
| `character/` | **完成（v1.0 M2，2026-10-07）**：角色载体 `data/characters/<cid>/`（`character.toml` + 三段占位 md），服务 `character.system_prompt(cid)`（**cid 必填**）/ `character.list` / `character.resolve`（空目录播种默认角色） |
| `webui/` | 完成：鉴权 / 仪表盘 / 审计 / 提供商 / 技能 / 配置 / 日志 / 知识库页 |
| `serve/` | **完成（v0.4.1）**：`aris serve` 一条命令起全套（缺则自建 PG、自启、预热 embedding、并入 WebUI），`--only/--skip/--dry-run` 可裁剪；**v1.0 M1（2026-10-07）**：组装根只装配一份进程级运行时（engine / registry / loop / skills），会话注入复用 |
| `store/` | 完成：便携 PG 17.11 + pgvector 0.8.1、embedding（本地 Bekko 384 维）、迁移 + 向量 helper；**可迁移性（v1.0 M0）**：二进制可运行验证 + 重获取、属主可操作报错、角色探测对齐、端口自动避让 |
| `knowledge/` | 首期完成：两表 / 分块 / 摄入 / 纯向量检索 / CLI / agent 工具 / WebUI 页 |
| `memory/` | **设计已定案（2026-09-29）**：内容模型见 `docs/developDoc/MEMORY.md`（分层 / 事件 / 两周记 / 惰性衰减 / 注入 / 表结构）；会话与消息表见 D2。**D16 = A 级，8 条待商讨已补完** |
| `voice/` | **占位**（选型见 `docs/developDoc/stt&&tts选型.md`） |
| `autorun/` | **方向已定，暂不实现（2026-09-28）**：纯调度器 + 触发源抽象（D11） |

- **入口**：`aris serve` 一条命令即可（首次自动获取便携 PG，需联网数分钟）；
  `aris doctor` 体检、`aris chat` 终端对话（调试用，与应用互不干涉）
- 测试：`uv run pytest` **131 passed**（DB 未运行则集成用例自动 skip）
- 数据库：便携实例在 `data/pg`，项目本地、不注册系统服务；`aris serve` 会按需自建/自启，
  退出时只停自己拉起的那个
- 知识库现有资料：`data/knowledge/刑法.md`（约 129 块）
- 待办方向：`docs/developDoc/BACKLOG.md`（8 条中长期，**2026-09-28 已全部过一轮商讨**）
- 已知陷阱（踩坑档案，修完就补）：`AGENTS.md`「已知陷阱」节

## 最近动态

### 2026-10-07：v1.0 M2 —— 角色载体（代码）

- **为什么**：人设原是模块常量 + 无参单槽服务，多人格没法各自挂；`chat/__init__.py`
  还包级直引常量，绕过总线。
- **做法**：新增 `character/carrier.py` 落地 `data/characters/<cid>/`（`character.toml` +
  三段只读占位 md；`cid` 创建时生成 uuid，改名 / 改人设不影响）；服务改为
  `character.system_prompt(cid)`（**必填**）/ `character.list` / `character.resolve`
  （缺省取最早一个，空目录播种默认角色，幂等）；serve 的 character 步骤补启动动作；
  `ChatSession` 增 `cid`，显式 `--system` 仍最高优先级且不碰角色目录。
- **测试**：`tests/test_character.py` 8 例（两角色不串 / 播种幂等 / `cid` 必填 /
  会话取人设）；`uv run pytest` **131 passed, 10 skipped**。
- **文档**：`docs/developDoc/{CMCB,SERVE,V1.0-PLAN}.md`、`AGENTS.md`。

### 2026-10-07：v1.0 M1 —— serve 上收组装根（代码）

- **为什么**：`ChatSession` 原来自己 new engine / registry / loop / skills，不先让它
  可注入，M3 落库时还得往会话构造里塞参数、白改一遍；且单进程多会话下**后开的会话会
  覆盖前面的**（单槽服务）
- **做法**：新增 `serve/assembly.py`（`build_engine` / `get_runtime` / `peek_runtime` /
  `reset_runtime`，模块级一份 `_runtime`）与 `behavior/runtime.py`（`BehaviorRuntime` =
  engine + registry + skills + loop，`system_prompt()` 拼工具提示 + 技能菜单）；
  `ChatSession(engine=..., runtime=..., ...)` 可注入、缺省懒取 `get_runtime()`；
  `assemble()` 末尾装配运行时（**失败只记警告不抛**，`aris doctor` / WebUI 仍能起）；
  serve `behavior` 步骤补上真实启动动作与「运行时已装配：N 个工具 / M 个技能」探针
- **顺手收掉一个隐患**：`loop` 不再持有 `model_id`（共享实例存模型 = "最后一个会话的
  模型"），改 `iter_events(..., model_id=...)` **按调用传**，`loop.set_model` 服务删除；
  loop 内部改**直接调**注入的 engine / registry（同一份装配对象），总线服务保留给外部用
- **不做 per-cid map**：D15 单一会话 + skills 本就是全局外部内容（`data/skills/`），
  真需要时在 `behavior/runtime.py` 里加（该文件 docstring 已留接缝）
- 测试：新增 `tests/test_assembly.py` 7 例（运行时幂等、服务指向那一份、两段会话不互相
  顶掉、模型按调用传、with_tools=False 的运行时）；`uv run pytest` **123 passed, 10 skipped**
- 文档：`CMCB.md`（服务表去 `loop.set_model` + 迁移状态）、`SERVE.md`（已知缺口 → 已完成）、
  `V1.0-PLAN.md`（M1 状态与落地）、`AGENTS.md`（serve 条「待做」改「已上收」）

### 2026-10-07：用户记下两件事 + 文档迁 `docs/`

- **文档目录已迁**：`developDoc/` → `docs/developDoc/`、`referenceDocumentation/` →
  `docs/referenceDocumentation/`（用户提交 `b00b2a6`），`README.md` 重写为用户向文档
  （旧版存为 `README.old.md`）——**本次把仓库内 33 个文件里 75 处 `developDoc/` 引用
  一并改成 `docs/developDoc/`**（代码 docstring 与配置注释也改了，否则新会话按 AGENTS
  文档索引找不到文件）
- **用户记的两件事**：
  1. **`config/` 迁到 `data/config/`** —— 目的：`data/` 成为换机时唯一要带的东西。
     **未定**：示例/模板配置（`providers.example.toml` 等）留在哪儿
  2. **云端支持**（**排 v1.0 之后**）：云端 embedding 容易；云端 SQL = 允许连**外部
     psql**（DSN 指向别人的库）。已记入 `docs/developDoc/BACKLOG.md`

### 2026-10-01：v1.0 M0 —— 可迁移性与启动幂等（D14）

- **目标**：换机 = 新机 `git clone` → 拷 `data/` → `uv run aris serve` 直接起。M0 排在
  最前是因为 **PG 角色名必须在建任何新表之前定死**（否则 memory 三表建在旧角色名下，
  将来统一角色名就变成真数据迁移）
- 四个缺口全部落地（实现都在 `store/pgenv.py` + `store/bootstrap.py`）：
  - **二进制可运行**：新增 `probe_runnable()`，真跑一次 `postgres --version`（文件在 ≠
    能跑）；`data/pg` 跑不起来 → `bootstrap_env(force=True)` 删掉这个**可重建**目录重获取，
    `data/pgdata` 绝不动
  - **属主**：新增 `ownership_error()`——属主不是当前用户就报**可操作错误**（不自动 chown）
  - **角色名**：新建集群统一 `initdb -U aris`（与主机无关）；老集群 `align_user()` 实连候选
    角色并写 `pgdata/aris-role` 标记。候选里加了 `legacy_role_hints()`——从 `pg_authid`
    数据文件里**离线扫**出角色名（换机后老主机用户名根本猜不到），命中仍以在线实连为准
  - **端口**：`choose_port()` 被占则向内核要空闲端口，**不写任何配置**；运行中实例端口
    留在 unix socket 文件名（`.s.PGSQL.<port>`）里，`aris db status/psql` 等独立进程反推
- **`data/` 分层**：新增 `datadir.py`（`CARRIED_PATHS` / `REBUILDABLE_PATHS`）；
  serve 新增 **`data` 步骤**幂等创建 `characters/` `skills/` `autorun/`；`aris doctor`
  打印分层完整性
- **顺手修一个真 bug**：崩溃后只清 `postmaster.pid` **不够**——run 目录里的
  `.s.PGSQL.*`（含 `.lock`）会让下一次 `pg_ctl start` 报 `lock file already exists`
  直接拒启；`_clear_stale_runtime()` 两类一起清（实测踩到）
- **实测**（都用真数据库跑过）：
  - 拷 `data/`（pg + pgdata + knowledge，231MB）到别处 → `aris doctor` 全绿 →
    `aris db start` 起得来 → `psql` 连得上（**换机三步成立**）
  - 占住 55432 → 自动改用 34557，`detect()` 在**另一个进程**里也能反推出 34557
  - `initdb -U otheradmin` 造集群（宿主是 kasamorin）→ 离线候选扫出 `otheradmin` →
    在线对齐成功 → 标记文件写入 → `psql` 实连 `otheradmin`
- 文档：`README.md` 新增「换机与迁移」小节、`SERVE.md` §4 新增缺口表与处理
- 测试：新增 `tests/test_store_portability.py`；`uv run pytest` **117 passed, 10 skipped**

### 2026-10-01：persona → character 改名（代码 + 文档）

- 用户定：模块名由 `persona/` 改为 **`character/`**（推翻同日早些时候「保留 persona」的决定）
- **代码**：`git mv src/aris/persona src/aris/character`；服务名 `persona.system_prompt` →
  `character.system_prompt`；serve 步骤名与探针 `_probe_character` 同步；`config/serve.toml`
  可选值、`tests/test_serve.py` 同步
- **文档**：`data/personas/` → `data/characters/`、`persona.toml` → `character.toml`，
  记忆分区列 `persona_id` → **`cid`**（与 D1 的 `cid` 收口）；全仓 21 个文件
- 验证：`uv run pytest` **103 passed, 10 skipped**
- **v1.0 施工开始**：M0（可迁移性与启动幂等）开工，方案见 `docs/developDoc/V1.0-PLAN.md`
### 2026-10-01：版本发行改三线 + 记忆形态微调（文档，未写代码）

- **版本发行改成三线、数字共用**（取代 2026-09-24 的 beta 方案）：
  `beta-vX.Y.Z`（开发时版，`__version__ = X.Y.Z.dev0`，发在 main）／
  `vX.Y.ZbN`（候选，只进 develop、不合 main）／`vX.Y.Z`（正式版，main）。
  dev 消耗掉的数字不再有正式版；攒够后正式版直接给目标号（如 `v1.1.0`）。
  三个脚本（`lib-version.sh` / `bump-version.sh` / `release-check.sh`）已按新规则改并实测
- **记忆形态微调**：权重改**整数「点」+ 位运算**（`w_eff = (weight + hit×100) >> floor(Δt/H)`，
  初始 100 / 阈值 500 / 封顶 800 / 消失 5，**无浮点**）；关键记忆注入上限 5 → **7**；
  角色 id 用 **`cid`**（创建时生成，改名/改人设不影响）；明确常驻三块注入在末条 user
  **之前**、12h 兜底检索结果在**之后**；新增 `aris memory` CLI 子命令（list / recompute /
  rebuild-index）
- **D8/D9/D10 移出 v1.0**（Responses API / 多模态底层 / 降级与成本纪律）
- **测试用本地小模型**：用户在后台部署本地小模型跑 v1.0 验证，规避 API 成本
- **单一会话 = 每角色一个**；明确不做"人格分裂"
- **`memory_search` 工具形态**：默认查三类提炼物（事件走向量、总结/两周记走关键词），
  可切 `scope=raw` 查原文；`mode=random` 做**加权随机**的主动随机回忆（不计 hit）；
  工具描述加"不必只查与当前对话相关"的提示
- **用户干预两条都要**：**钉住**（不衰减）+ **可见性** `normal|private|sealed`；
  WebUI `/memory` 另加**统计**与**批量管理**
- **模块名 `persona` → `character`（人格）**（当日原定 persona，同日改），id 用 `cid`
- **测试用本地小模型**：只做测试用（用户稍后接入）；embedding 本来就是本地
  Bekko a25m（384 维，不花钱）

### 2026-09-29：D16 记忆内容模型商讨补完（全部定案，未写代码）

- **补完的 8 条**（原列在 `docs/developDoc/MEMORY.md` 第五节，现已搬进「定案」各节）：
  - **衰减**：`w_eff = (weight + hit) × 2^(−Δt/H)`，H 二级 14 天 / 三级 180 天；
    **读时惰性计算、不落库**（`autorun` 已搁置，这是唯一可行形态）→ 调参不用洗数据
  - **防刷分**：`+1` 只在真实检索命中时发生（注入不算）、一次调用内去重、封顶 8.0、
    涨到关键阈值 5.0 后不再靠命中上涨
  - **两周记（用户折中定案）**：**取消周记 / 月记**，二级窗口 = 14~15 天、只出「两周记」；
    聚合输入 = 该窗口的对话总结 + compact 摘要
  - **注入**：三块 = 关键记忆 ≤5 条 / 近 14 天事件 ≤10 条 / 最近两周记 1 篇；
    **不设 token 预算**（窗口是 compact 的事）；记忆块拼在**历史尾部、不写进 history**（保 KV cache
    前缀）；DB 异常则跳过注入继续聊
  - **compact 与记忆**：`system prompt` 与记忆块**都不参与压缩**，压缩后重新拼回；
    重组 = system + 记忆块 + 〔**摘要 + compact 前最后 3 条原文**〕（为了"顺下来"）；
    compact 摘要**落库**（`kind=compact`），查询时按 kind 分开取
  - **调用时机**：默认 **Aris 自主调 `memory_search`**；**兜底**——超 12 小时没用过记忆检索，
    下一轮主动用用户原问题检索、把结果**插在询问之后**
  - **表结构**：二三级**同表** `memory_entries`（`tier` 按时间 + `kind` 区分）；
    **只有事件向量化**（`embedding` 可空），总结/两周记**不向量化**（否则会检索到残缺周记），
    靠**时间直取**
  - **WebUI**：`/memory` 页 = 列表 + 改权重 + 软隐藏/恢复 + **硬删除**（二次确认，
    只删提炼物、不动原文），页面上不触发 LLM
  - **热冷收敛**：v1.0 只建热表 384 维，冷库将来新建表、不迁移
- **顺带**：事件抽取**回归样例**补了 5 条（3 正 2 反，按真实对话写，带寒暄干扰 / 工具调用 /
  无结果协商 / 情绪类），落进 `MEMORY.md` 2.3，实现时搬进 `tests/`
- **文档同步**：`MEMORY.md` 状态改「定案」、颗粒度表 **D16 由 B 改 A**、结论回到
  「v1.0 主线全 A 级、无挂起项」；`AGENTS.md` / `BACKLOG.md` 同步

### 2026-09-29：对齐 D1–D16 颗粒度（文档整改，未写代码）

- **起因**：2026-09-28 那份商讨记录落盘后，编号与结论口径在四处对不上，用户要求复核对齐
- **发现并修掉**：① 编号范围四种说法（`D1–D13` / `D1–D15` / 实际到 **D16**）→ 统一 **D1–D16**；
  ② **D13 一号两义**（讨论稿 D13 = 其他收尾；`AGENTS.md` / 本文件当成 WebUI 配置页，
  而后者原本只是 D11 尾部一条无编号的「顺带记入待办」）→ 收编进 D13；
  ③ 颗粒度表缺 **D4 / D13 / D16** 三行、并自造了一个不存在的 `D15b` → 补齐 16 行、
  `D15b` 改为 D15 子项；④ A 级定义（"取值也定死"）与标 A 的行内容（"实现时调"）冲突 →
  放宽定义；⑤ 结论「**没有任何挂着的待商讨项**」被 D16 / `MEMORY.md` 推翻 → 改写为
  「除 D16 外主线全 A 级」
- **用户当场决定**：**D16（记忆内容模型）进 v1.0**，但其 **8 条待商讨必须先补完**
  （原 7 条 + 热冷两轴表结构收敛）→ 已同步到 `AGENTS.md` / `MEMORY.md` / 本文件「当前聚焦」
- 顺带修：`discuss-2026-09-28.md` D5 里与 D16 矛盾的「暂不做大会话结束写记忆」；
  `SERVE.md` 示例输出里过时的「43 个总线服务」（现为「各模块声明的 24 个依赖服务」）；
  本文件「现状速览」`core/` 行的 43（实测 core 16 个 / 全项目 52 个注册点）

### 2026-09-28：BACKLOG 8 条全量商讨（纯商讨，未写代码）

- **目标**：为国庆前后发布 **v1.0**（memory + character 基础功能）铺路，一次性把 8 条
  BACKLOG 全部过完；按 v1.0 相关性排序商讨
- **方法**：8 个只读子代理并行做代码级勘察（产出含 `文件:行号` 的卡片）→ 逐条拍板；
  产物 = **`docs/developDoc/discuss-2026-09-28.md`**（勘察卡片 + D1–D16 定案/商讨）
- **核心定案**（完整见该文件与 `AGENTS.md`「BACKLOG 全量商讨定案」）：
  - **D1 人格**：「多人格」= **多个人**（各自会话/记忆）；载体 = `data/characters/<id>/`
    文件；**单进程多会话**；**记忆按 `cid` 分区**
  - **D2–D5 会话与压缩**：小会话是**先天属性**（不需切）；**大会话 = 纯时间聚类**
    （k=2 的 1D k-means ⇒ 取最大消息间隔切分）；**compact 后同一会话继续**；
    原文全量保留 + 可归档；触发用字符估算 × `context_length` 比例
  - **D6 对外接口**：双层门面、CMCB 为载体 → **搁置，v1.0 只文档化**
  - **D7 Skills**：**整体迁 `data/skills/`**；包内不留技能；3 个测试用 skill 暂放
    `docs/developDoc/skills-backup/`
  - **D8/D9 提供商**：**支持 Responses API**；多模态只做底层；思考模式默认关闭走配置；
    **模型级 `free` 标签 + 免费优先降级**；`race_fallback` 默认关、SDK 内建重试关掉
  - **D10 多模态**：模型补标模态；图片落盘按引用；视觉三挡 `none|auto|force`
  - **D11 autorun**：新模块 = **纯调度器 + 触发源抽象**；任务实例落
    `data/autorun/tasks.toml`；**同日追加决定暂不实现（v1.0 也不做）**，只留设计文档
  - **D12 文档站**：**短期不做**
- **补充两条 v1.0 硬目标（D14/D15，用户当场追加，权威文档
  `docs/developDoc/PORTABILITY-AND-SINGLE-SESSION.md`）**：
  - **D14 可迁移性**：换主机 = 新机 clone + 把 `data/` 全量拷过去 + `uv run aris serve`
    直接起；不写死绝对路径、启动幂等、跨平台能重获取 PG
  - **D15 单一会话原则**：只有一个当前会话，**不做也不允许子代理**；一切输入进同一会话；
    复用最新小会话 + 冷却 3~5 天（吃 KV cache 省钱）；场合/去向模型只写文档暂不实现
- **顺带勘误** `docs/developDoc/API-CALL.md`：第 3 节 Responses 整节重写（原路径/模型名/
  兼容性描述均过期）、第 4 节重写思考模式 + 新增 4.3 图像理解 / 4.4 文件输入 /
  4.5 模态元数据 / 4.6 Files API / 6.1 落地要点
- **同步改动**：`AGENTS.md`（模块划分加 `autorun/`、文档站改「短期不做」、待定划掉
  人格载体、新增「BACKLOG 全量商讨定案」节、文档索引加一行）、`BACKLOG.md`（每条加
  「商讨结论」+ 速览表）、`WEBUI.md`（会话模型按 D2/D5 修订）、`PLUGIN.md`（标注搁置）
- **未写代码**；该轮文档已由用户提交为 `a883e2c`（docs: BACKLOG 8 条全量商讨定案）

### 2026-09-24：v0.4.2 发布（首个带 beta 标记的版本）

- **为什么是 v0.4.2 而不是 v0.4.5**：serve 是「clone 下来一条命令起服务」的体验入口，
  本打算攒到 v0.4.5；但 memory / character 从开发到完善可能吃掉好几个版本号、把 v1.0
  提前，于是 serve 收在 v0.4.1，把 v0.4.2 留给**真实走一遍新的版本机制**
  （上一轮只是 0.4.1 → 0.4.2 → 回滚的演练，不算真发布）
- **本版内容** = v0.4.1 的全部能力（serve 一条命令起服务）+ 版本机制与发布规范落地：
  - 版本号改成单一来源（`src/aris/__init__.py`）：pyproject 走 dynamic、uv.lock 不再
    记录本项目版本。**bump 实测只改了 `src/aris/__init__.py` 一个文件**，uv.lock 零变更
  - **beta 标记规范**：0.x 全段为 beta（正式版留 v1.0.0），tag 带 `-beta` →
    `v0.4.2-beta`；v1.0.0 起正式版 `vX.Y.Z`、预发布 `vX.Y.Z-beta.N` 且 `__version__`
    同步写 `1.3.0b1` 形式。规则收在 `scripts/lib-version.sh`，两个脚本共用
  - README 标题下加发布公告（隆重发布 v0.4.2 + 一句话功能概述）
- **发布流程**：`bump-version.sh 0.4.2` → `release-check.sh` **PASS** →
  合并 `main` → tag `v0.4.2-beta`
- 测试：`uv run pytest` **103 passed, 10 skipped**

### 2026-09-24：版本号改为单一来源（第三条开发规范）

- 背景：版本号原先在 `pyproject.toml` / `src/aris/__init__.py` / `uv.lock` **三处各写
  一遍**，0.2.0 / 0.2.2 / 0.2.6 每个版本都要额外的「同步 uv.lock / `__version__`」提交，
  v0.4.1 还误把版本行混进了功能提交。回望全部提交后定案——**检查脚本只能治症状，
  改成结构上只剩一处**
- **唯一源 = `src/aris/__init__.py` 的 `__version__`**：`pyproject.toml` 改
  `dynamic = ["version"]` + `[tool.setuptools.dynamic] version =
  {attr = "aris.__version__"}`；**`uv.lock` 不再记录本项目版本**（实测 `uv lock` 把
  `version = "0.4.1"` 那行删掉了），于是「三源同步」这个动作本身消失，也不再有同步提交
- **两个实测踩坑（已进 AGENTS「已知陷阱」）**：① uv 默认只按 `pyproject.toml` 判定
  元数据缓存，改了 `__init__.py` 也不重建（实测 `uv sync` 后仍是旧版本）→ 必须加
  `[tool.uv] cache-keys = [{ file = "src/aris/__init__.py" }]`；② 版本号必须能被
  setuptools 解析为 PEP 440（`9.9.9-test` 直接 `InvalidVersion` 构建失败）
- 新增 `scripts/bump-version.sh <版本|patch|minor|major>`：校验干净 develop / 版本合法 /
  tag 未占用 → 改源 + `uv lock` + `uv sync` → 打印提交与发布命令（**只改文件不提交**）
- `scripts/release-check.sh` 重写为六项：单一来源结构（pyproject 不得再有静态 version、
  必须有 dynamic + attr + cache-keys）、已安装元数据一致、`uv lock --check`、分支为
  develop、无未合并分支、目标 tag 未占用；各失败分支已逐条实测
- `AGENTS.md`：「Git 开发流程」里两条过时描述改掉，新增**「版本号更新（2026-09-24
  定案）」**小节，「已知陷阱」新增「打包 / 版本」分组
- 验证：`aris --version` → `Aris 0.4.1`；release-check 在 feature 分支如实报
  FAIL（分支 + tag），在 develop 上结构项全绿
- **本次不改版本号**：只改机制，版本仍为 v0.4.1

### 2026-09-19：serve 收尾（v0.4.1 —— 首个「clone 下来一条命令起服务」的版本）

- **缺则自建**：`store.start(init_if_missing=...)`——便携实例不存在时直接
  `bootstrap_env()`（micromamba + conda-forge，联网首次数分钟），用户不必先敲
  `aris db init`；开关 `config/serve.toml: init_db`（默认开），探针相应报
  「未初始化（启动时将自动获取）」
- **退出语义定案并落地**（SERVE.md 新增小节）：`0` 正常（含 Ctrl-C 正常收尾）、
  `1` required 失败或 WebUI 起不来、`2` 参数写错、`130` 收尾期间再次 Ctrl-C 强制退出
  （日志提示库可能仍在跑、用 `aris db stop`）
- **README 快速开始改为 `aris serve` 一条命令**，补调试选项与 CLI 表
  （serve / doctor / web / db / knowledge）
- **端到端实测**（真实 `aris serve`，无参数）：PG 自启 → embedding 后台预热 →
  `/` 与 `/knowledge` 均 200 → SIGINT → uvicorn 优雅关闭 → 停掉自己拉起的库 →
  **退出码 0**，库回到停止态
- 测试 `uv run pytest` **103 passed, 10 skipped**（新增「缺则自建」探针分支用例）

### 2026-09-19：serve 收尾——组装根上收 + doctor 合流探针（SERVE.md 第 4–5 步）

- **唯一组装根**：`serve.assemble()` 成为唯一一份「import 哪些所有者模块」的清单；
  `webui.create_app()` 只搭 HTTP 层（原先它自己 import `llm.fetch`/`llm.manage`/
  `skills` 并调 `_verify_bus_services()`，与 `cli.py` 那套重复、必然漂移）；
  测试改在 `tests/conftest.py` 调 `assemble()`（测试也是宿主）
- **依赖清单仍归各模块自己声明**：`webui._REQUIRED_SERVICES` → 公开的
  `webui.REQUIRED_SERVICES`，由新增的 `services` 步骤（required）统一核验——原实现
  只有 WebUI 那条路径会被检查
- **`aris doctor` 合流**：环境自检（Python / C 扩展 / .env / 数据目录）+
  `serve.probe_all()`，与 `aris serve --dry-run` 走同一条探针路径；LLM 体检收敛为
  总线服务 `llm.providers.check`（`aris llm check`、doctor、serve 探针共用一份结论，
  原先判断散在 CLI 里）
- 顺带：serve 的 `core.llm` 探针现在会把体检错误直接报出来（`✗` + 首个错误 +
  `aris llm check` 提示），不再只数提供方个数
- 实测：`aris doctor` 八项探针全绿并给出可操作结论；`aris serve --dry-run` 8 步；
  `aris web` 起服务 GET `/` → 200，第二个实例被端口探测拒绝（exit 1，错误文案明确）；
  `uv run pytest` **102 passed, 10 skipped**
- 剩余缺口（SERVE.md §10）：工具注册表 / agent loop / LLM engine 仍是会话级对象，
  等 #4/#7 时由 serve 上收；退出细节（二次 Ctrl-C、退出码明细）待定

### 2026-09-19：serve 首期实现（`aris serve` 可用）

- 新增 `src/aris/serve/{__init__,conf,steps}.py`：组装根 `assemble()`（集中 import 触发
  注册）、步骤表（探针 + 启动动作）、编排（`--only` 依赖闭包 / `--skip` 硬排除 /
  失败分级 / 启动清单 / 收尾）；新增 `config/serve.toml`
- 各模块补启动 hook：`store.start|stop|db_status|embed_preload|embed_status`
  （含 `LocalBekkoProvider.warmup()`）、`knowledge.start`、`webui.probe|start`
  （`port_in_use()` 端口探测，`aris web` 也走同一道）；`core.bus.services()` 列出
  已注册服务
- CLI：`aris serve [--only a,b] [--skip c] [--dry-run]`；并把 `serve` / `web` 的控制台
  日志级别固定 INFO——**启动清单被 WARNING 阈值吞掉就等于没有**
- 实测：`--dry-run` 七步探针全绿（PG 未运行时 knowledge 报「待数据库启动后建表」而非红）；
  真实 `aris serve --skip webui`：PG 自启（顺带清残留 pidfile）→ 迁移 → embedding 后台
  预热 → knowledge 1 文档/129 块 → 退出时停掉自己拉起的库；无阻塞步骤时不执行收尾
  （否则「起了又立刻停」，`--only store.db` 这种用法会彻底没用）
- 测试：`tests/test_serve.py` 9 例；`uv run pytest` **102 passed, 10 skipped**
- 待做（SERVE.md 第 4–5 步）：上收 `webui` 的 import 与 `_REQUIRED_SERVICES`、与
  `aris doctor` 合流探针；工具注册表 / loop / LLM engine 仍是会话级对象（#4/#7 时上收）

### 2026-09-19：serve 模块方案定案（启动编排，`docs/developDoc/SERVE.md`）

- 定位：`aris serve` = **组装根 + 启动编排（相当于 init）**——把各模块按序拉起、前台
  打印启动清单与日志、`Ctrl-C` 收尾；**单向**（只调别人的启动动作，**不对外提供查询
  服务**）、**非守护**、**不含 TUI**
- 定案要点：
  - **PG 没跑就自启**；退出时**只停「自己拉起的」那个**（启动前探活为假才算自己起的）
  - **embedding 启动即后台预热**（+ 就绪标志）——懒加载会让首个工具调用顶穿 timeout
  - **WebUI 默认并入**；端口被占则**拒绝启动 webui 并提示**，其余模块照常，不整体退出；
    `aris web` 保留并加同一道端口探测
  - **失败分级**：required 仅 `store.db`，其余 optional；降级/跳过/拒绝**一律记日志**
    并给可执行提示（严禁静默降级）
  - **调试选项** `--only` / `--skip` / `--dry-run` + `config/serve.toml`（CLI 覆盖配置）
- 顺带收口：`cli.py` 与 `webui/__init__.py` 里重复的 import 与 `_REQUIRED_SERVICES`
  自检**上收到 serve**（现在两处各一套，已存漂移风险）；`aris doctor` 与 serve
  共用探针；WebUI 仪表盘「系统状态区域」直接读各模块服务，不经过 serve
- 新增 `docs/developDoc/SERVE.md`（定位/三类服务/启动顺序/自启策略/失败分级/配置/接缝/
  实现次序）；`AGENTS.md` 模块划分与文档索引同步
- 商讨补充定案：**`aris chat` 是纯前端，与 serve 互不干涉**（既不自启也不被自启，
  不触发 PG 自启与预热）；**人格与对话历史的载体先置着**（`data/characters/` 文件 vs
  PG 表、会话是否落 PG —— 做 #4/#5 前必须先定，记入 BACKLOG #4 与 AGENTS 待定）
- **下一步：按 SERVE.md 第 10 节开始实现 serve**；真 API 实测等用户找低成本方案
- 未写代码，实现次序见文档第 10 节

### 2026-09-19：精简 PROGRESS.md + `.workbuddy/` 进 gitignore

- `PROGRESS.md` 只留当前进度（现状速览 / 最近动态 / 当前聚焦 / 路线），历史条目
  原文移至 `docs/developDoc/PROGRESS-ARCHIVE.md`；此后只在顶部追加、阶段性搬运
- `.gitignore` 补 `.workbuddy/`（本地工具目录，不入库）
- 踩坑记录分层：**会重复咬人的一行进 `AGENTS.md`「已知陷阱」**（每个会话自动读到），
  长篇叙述留在当轮条目、过时随归档下沉
- 纯文档改动，未提交

### 2026-09-19：建立后续待办清单（`docs/developDoc/BACKLOG.md`）

- 7 条中长期方向落 `docs/developDoc/BACKLOG.md`：① 提供商与 LLM 协议更新优化
  ② Skills 迁到 `data/skills/` ③ 开放各模块对外接口（插件系统底座）④ 多人格并行
  ⑤ 上下文压缩（属记忆系统）⑥ 多模态支持 ⑦ 自动任务与主动操作
- 依赖速查：#3 是 #4/#7 的底座；`store/` 已就位 → #5 可开工；#2 独立可插队
- `AGENTS.md` 文档索引加一行指向本文件

### 2026-09-19：总线文档与注释统一改名 CMCB

- 定名「跨模块通讯总线」（CMCB）落到**称谓层**：架构文档 `BUS-ARCHITECTURE.md`
  → `CMCB.md`（git mv 保留历史），`AGENTS.md` / `README.md` 与 src 五个文件的
  注释 / docstring 同步；**代码标识符（`core/bus.py`、函数名、服务名）保持不变**
- 验证：`uv run pytest` 93 passed, 10 skipped；合并 `docs/cmcb-rename` → `develop`

### 2026-09-18：v0.4.0 发布（知识库首期）

- 三源 bump v0.4.0 → 合并回 `main` → 打 tag `v0.4.0`；本版 = `store/` 地基 +
  `knowledge/` 首期 + agent 工具 `knowledge_search` + WebUI 页 `/knowledge`
  （同版带来免鉴权模式：未配密码时只绑回环）
- 同版修三个真 bug：WebUI 上传后无限刷新、`is_running` 误判、残留 pidfile 挡启动
  （细节见归档）

## 当前聚焦

**目标：国庆前后发布 v1.0**（memory + character 基础功能；文档站、对外接口、autorun、
知识库第二阶段等**已明确挤出 1.0**，见商讨 D6/D11/D12）。决策依据全部在
`docs/developDoc/discuss-2026-09-28.md`（结合 `AGENTS.md`「BACKLOG 全量商讨定案」）。

> **前置项：无**。D16 的 8 条待商讨已于 2026-09-29 全部拍完（`docs/developDoc/MEMORY.md`
> 已改「定案」、颗粒度表 D16 = A），v1.0 主线无挂起项，只剩实现时调的参。

> **施工方案（阶段划分 / 每阶段改动面 / 验收 / 风险）见 `docs/developDoc/V1.0-PLAN.md`**，
> 下方是主线摘要。
>
> **施工进度（M0–M9）**：**M0 ✅**（2026-10-01，可迁移性与启动幂等）→
> **M1 ✅**（2026-10-07，serve 上收 / 组装根）→ **M2 ✅**（2026-10-07，角色载体）→
> **下一步 M3**（会话与消息落库）。

**v1.0 主线（按依赖顺序）**：

1. **可迁移性 + 单一会话**（D14/D15，硬目标，权威文档
   `docs/developDoc/PORTABILITY-AND-SINGLE-SESSION.md`）：`data/` 分层可迁移自检、
   跨平台 PG 重获取、`pgdata` 属主与端口缺口；会话复用最新小会话 + 冷却 3~5 天 +
   串行排队 + 消息带场合/说话者
2. **人格载体 + 会话落库**（D1/D2，`character/` + `memory/`）：`data/characters/<id>/` 文件、
   `cid` 贯穿、`memory_sessions` / `memory_messages` / `memory_conversations`
   三表（owner=`memory`，用 `store/` 迁移机制）
3. **大会话分组**（D3/D4）：按消息时间戳做 k=2 的 1D k-means（取最大间隔切分），
   物化 + 可重算
4. **上下文 compact**（D5）：同一 `session_id` 内摘要替换；字符估算 × `context_length`
   比例触发；原文保留 + 可归档
5. **记忆内容模型**（D16，`memory/`，**已定案**）：事件 / 对话总结 / **两周记**（总结类不向量化）；
   `w_eff` 惰性衰减 + 命中 +1（一次调用内去重、封顶 8.0）；注入三块（关键记忆 / 近 14 天事件 /
   最近两周记，**不设 token 预算**、拼在历史尾部）；compact 后重拼（摘要 + 前 3 条原文）；
   `memory_search` 自主调用 + 12 小时兜底；`memory_entries` 同表 + `/memory` 页（含硬删除）；
   只建热表 384 维
6. **WebUI**：配置页体验重做（D13，"选项名 + 数值框"要改）+ `/history` 页按会话模型落地

**v1.0 附带（同批做的底层能力）**：
- **Skills 迁 `data/skills/`**（D7，改动小可插队）

> **2026-10-01 定**：**Responses API / 多模态底层 / 提供商降级与成本纪律
> （D8/D9/D10）整条移出 v1.0**（时间已进 10 月，v1.0 只保 memory + character），
> v1.0 之后再做。

**明确不做（1.0 之后）**：对外接口/插件（D6）、文档站（D12）、
**Responses API / 多模态底层 / 降级与成本纪律（D8/D9/D10，2026-10-01 移出）**、
**autorun 定时与主动任务（D11，2026-09-28 追加决定暂不做）**、
目标/计划状态层、场合/去向（含独白）、知识库第二阶段（PDF/混合检索）、语音链路

**遗留低优先级**：serve 收尾（SERVE.md 第 4–5 步）、真 API 实测、WebUI 仪表盘系统状态区域、
htmx / Lucide（可选）

## 开发路线

1. ✅ 项目骨架（2026-08）
2. ✅ 接入 LLM（2026-08-09）
3. ✅ 跑通文字对话（2026-08-09）
4. ⬜ 记忆系统（PostgreSQL + pgvector）—— **v1.0 主线**（载体已定：D1/D2），
   `memory/` 复用 `store/`
5. ⬜ 人格系统 —— 提示词工程已起步（2026-08-12）；**v1.0 要把载体与多会话落地**（D1）
6. ⬜ 语音链路（STT → LLM → TTS）
7. ✅ 行为扩展：函数调用（2026-08-09）、联网搜索（2026-08-09）、skills（2026-08-12）；
   MCP 待后续
8. ⬜ GraphRAG
9. ✅ 知识库首期（v0.4.0）；第二阶段 PDF + 混合检索待做，详见 `docs/developDoc/KNOWLEDGE-BASE.md`
10. ⬜ autorun（定时与主动任务）—— **方向已定，暂不实现**（D11，只留设计文档）


---

# 附：更早的归档（原 docs/developDoc/PROGRESS-ARCHIVE.md）

# 开发进度归档（至 2026-09-18）

> `PROGRESS.md` 只保留**当前**进度；本文件保存已翻页的历史条目（原文照搬，不再更新）。
> 归档范围：2026-08-23 v0.3.0 ~ 2026-09-18 v0.4.0（含各次踩坑记录）。
> 维护方式：`PROGRESS.md` 顶部持续追加新条目，阶段性把旧条目整体搬到本文件末尾。
> **注意**：其中仍会咬人的坑已抽成一行一条收进 `AGENTS.md`「已知陷阱」，
> 本文件对应条目只作来龙去脉参考。

### 2026-09-18：版本 v0.4.0 发布（知识库首期）

- 版本号三源同步 bump 至 **v0.4.0**（minor 级：新增知识库整块能力）
- 本版内容：
  - **`store/` 模块（新）**：便携 PostgreSQL 17.11 + pgvector 0.8.1（micromamba +
    conda-forge，免 root；`aris db init|start|stop|status|psql|migrate`）、embedding
    抽象 + 本地 Bekko a25m（384 维，`aris store info|embed`）、迁移机制与 pgvector
    helper，共 10 个总线服务
  - **`knowledge/` 模块（新）**：两表迁移、标题层级分块 + 定长兜底重叠、
    md/txt/html 摄入（content hash 幂等 + 软删重建）、纯向量检索（带来源与距离）、
    CLI `aris knowledge add|list|remove|search|reindex`
  - **agent 工具 `knowledge_search`**：与 `web_search` 并列、由 Aris 自主调用
  - **WebUI 知识库页 `/knowledge`**：上传落盘 + 后台摄入 + 轮询进度、文档列表/移除、
    检索试验、重建索引；同版还带来**免鉴权模式**（未配密码时自动只绑回环）
- 合并路径：`feat/knowledge` → `develop`（--no-ff）→ `main`，打 tag `v0.4.0`
- 测试：`uv run pytest` **103 passed**
- 下一步候选：真 API 实测（Aris 是否主动查库）/ 知识库第二阶段（PDF、混合检索）/
  记忆系统（`memory/` 复用 `store/`）

### 2026-09-18：修知识库页「上传后无限刷新」（模板 JS 死循环）

- 现象（用户报）：网页说上传完了，但页面不停 `GET /knowledge/jobs/<id>` 并反复刷新
- 根因：模板里用 `sessionStorage` 做「只刷新一次」的守门，却在**每次加载时先清掉**它：
  任务完成后 `location.reload()` → 守门被清 → 判定"已完成" → 再 reload，无限循环。
  另外还写了 `jobs[0]` 兜底，等于没有 `job` 参数时也会轮询最近一次任务
- 重写为有明确终止条件的形式：
  - 轮询只在「URL 显式带 `?job=` **且**该任务仍在 pending/running」时发生；
    这个判定由**服务端**写进 `data-poll`，测试可直接断言，不靠读 JS
  - 终态（done/failed/任务不存在）一律 `location.replace('/knowledge')`——
    URL 丢掉 `job` 参数 → 不会再进轮询/刷新分支，**循环在结构上不可能发生**
  - 不带参数时进度面板静态显示"最近一次任务"，不轮询
  - 任务 id 不存在（WebUI 重启过）显示「任务已过期」，同样不轮询
- 顺带修：Jinja 里 `job.items` 被解析成 **dict 的 `.items` 方法**（`TypeError:
  'builtin_function_or_method' object is not iterable`），改用 `job["items"]`
- 测试：新增 3 例回归（完成态 `data-poll=false` 且不再含 `sessionStorage`、
  进行中才轮询、过期任务只提示不轮询）；并让知识库用例**失败也清理**临时文档
  （上一轮失败的用例把 `/tmp/.../kb-webui.md` 漏在了真实库里，已清理）、
  断言改用**完整路径**且容忍库里已有别的文档（用户已投喂 `刑法.md`，129 块）
- 实测：`uv run pytest` **103 passed**；真实服务验证：上传 → running（约 21s
  加载本地模型）→ done → 完成态页面 `data-poll="false"`、收尾为
  `location.replace('/knowledge')`
- 用户侧注意：旧标签页里的 JS 还在循环，**关掉重开**即可

### 2026-09-18：修「数据库未运行」的两个真 bug（is_running 误判 + 残留 pidfile 挡启动）

- 现象（用户报）：WebUI 知识库页显示 `connection failed ... Connection refused`；
  手动 `aris db start` 又报 `lock file "postmaster.pid" already exists /
  Is another postmaster (PID 12) running`
- **bug ①**：`is_running()` 用 `pg_isready` 退出码判定时只认 `0`（接受连接），
  但**服务器在线却拒绝本次探测**（默认库不存在 / 正在启动中）返回 `1`，被误判成
  "没在跑" → 启动流程会去重复启一个已在跑的实例。现改为 `0/1` 都算在跑
  （`2` 无响应才算停），并把退出码语义写进注释
- **bug ②**：崩溃 / 命名空间回收后残留的 `postmaster.pid`（PID 被复用）会让
  `pg_ctl start` 直接拒绝启动。现 `start()` / `stop()` 先探测，确认服务无响应后
  清理残留 pidfile 再继续（`_clear_stale_pidfile`，带 warning）
- WebUI：数据库不可用时的报错换成可操作文案
  「数据库未运行：在项目目录执行 `aris db start` 后刷新本页」——`status()` 内部
  吞异常与路由兜底两条路径都要转，否则只转一条仍会漏（实测踩到）
- 实测：`aris db start` 自动清理残留 pidfile 后成功启动（PG 17.11 + pgvector 0.8.1）；
  `uv run pytest` **100 passed**；真实服务验证：库在跑时页面显示「文档 N · 块 M」，
  停库后显示友好提示
- 运维备注：便携实例是**项目本地**的，不随开机自启、也不注册系统服务——
  重启或长时间不用后，用 WebUI 前先 `aris db start`（要局域网用还需设
  `ARIS_WEBUI_PASSWORD`，见上一条）

### 2026-09-18：WebUI 免鉴权模式（未配密码时可直连，只绑本机）

- 起因：没设 `ARIS_WEBUI_PASSWORD` 时 WebUI **进不去**——`check_password()` 恒返回
  False，登录永远失败（不是崩溃，是卡在登录页）
- 定案（用户拍定）：未配置密码 → **免鉴权模式**，但监听地址**强制降级为回环**
  （护栏），避免默认 `0.0.0.0` 把管理后台裸奔到局域网
- 实现：
  - `auth.resolve_bind_host()`：无密码时非回环地址一律降级 `127.0.0.1` 并返回提示；
    有密码原样放行——`aris web` 启动时打印该提示（实测传 `--host 0.0.0.0` 也只绑本机）
  - 中间件走**显式免鉴权分支**（不是松匹配放行，避免重蹈 `/loginfoo` 绕过鉴权的覆辙）；
    另打一条「运行在免鉴权模式」warning，绝不静默放开
  - `/login` 无密码时 302 回 `/`；导航隐藏「退出」、显示「免鉴权模式（本机）」
    （`render()` 统一注入 `auth_disabled`）
- 顺手修：`/knowledge` 在数据库未运行时直接 500（`knowledge.sources` 未兜住）
  → 现在状态区显示原因、列表为空、页面照常 200；移除/重建索引失败也只记日志不炸页面
- 实测：`uv run pytest` **99 passed**；另起真实服务验证：无 cookie 直访 `/` 与
  `/knowledge` 均 200、导航无「退出」、`/login` 302 回首页、uvicorn 实际只监听
  `127.0.0.1:9692`

### 2026-09-18：WebUI 知识库页（上传 → 后台摄入 → 轮询 → 检索试验）

- 方案（用户拍定）：**上传落盘 `data/knowledge/`（同名覆盖）**、**后台任务 + 状态查询**、
  **轮询进度**、实测先用 mock
- `knowledge/` 侧：新增 `safe_filename()`（取 basename + 替换分隔符/控制字符，
  落盘前再校验父目录，防穿越）、`KnowledgeService.upload()`（限额校验 → 落盘 →
  复用 ingest，坏文件逐条降级为 failed）、`status()`（开关 / 上传限额 / 文档与块计数）；
  新总线服务 `knowledge.upload` / `knowledge.status`，store 补 `store.vector.count`
- WebUI 侧：新增路由 `/knowledge`（页面）/ `/knowledge/upload` / `/knowledge/jobs/{id}`
  （轮询 JSON）/ `/knowledge/remove` / `/knowledge/reindex`，模板 `knowledge.html`，
  导航加「📚 知识库」，`_REQUIRED_SERVICES` 补 8 项
- 后台任务登记表 `webui/tasks.py`（内存态、保留最近 20 条、异常收敛为 failed）：
  摄入要跑本地 embedding（CPU 密集），不能在请求里同步跑，否则单 worker 整站被拖住
- 检索路由刻意用**同步 def**：首次检索要加载本地模型（约 20s），走线程池不阻塞事件循环
- 修一处测试污染：迁移 drift 用例往**全局登记表**塞重名版本，导致同进程后续所有迁移
  被判漂移（WebUI 上传随即 failed）。给 `migrate.run/pending` 加 `migrations=` 显式传参，
  测试改用局部列表，全局表只放真实迁移
- 实测：`uv run pytest` **93 passed**（含 WebUI 上传→列表→检索→移除、以及
  「WebUI 上传 → Aris 自主 knowledge_search 作答」的 mock 全链路）；
  另起真实 `aris web` 服务验证：登录 303、`/knowledge` 页面元素齐全、导航含知识库、
  启动日志无总线服务缺失
- **下一步**：真 API 实测（问一个投喂过的问题看 Aris 是否主动查库）；
  之后 PDF / 混合检索（第二阶段）或转记忆系统

### 2026-09-18：agent 工具 `knowledge_search`（脚本化 mock 验证工具往返）

- 新增 `behavior/tools/knowledge_search.py` 并接入内置工具集：D1 定案落地——
  与 `web_search` 并列，**由 Aris 自主调用**，不做每轮自动 RAG 注入；
  工具只是薄壳，能力经总线 `knowledge.search` 取（不直接 import 业务实现）
- 返回格式（D3）：外层 JSON
  `{"type": "knowledge_search_results", "query", "count", "results"}`，
  内部 markdown 省 token，每条为
  `id. 标题｜路径 › 标题层级（距离 x.xxx）` + 缩进内容（单块截断 800 字）
- **带距离是有意为之**：C4 定案「初期不设相似度阈值」，纯向量检索对无关查询
  同样返回最近片段（实测 `0.229` 强相关 / `0.672` 弱相关），把距离交给 Aris
  判断比硬设阈值稳妥；已写进 KNOWLEDGE-BASE 5.4
- 失败一律宽容降级（返回 JSON 说明，不抛到 UI）：query 为空 / top_k 非法 /
  总线异常 / 库为空 / 知识库关闭
- 测试 `tests/test_knowledge_tool.py` **7 例**：返回格式与来源标注、top_k、
  弱命中带距离、关闭态、空结果（替换总线调用，无需库）、参数非法，
  以及**脚本化 mock 的 agent loop 往返**（第 1 次请求回 tool_calls → 工具执行 →
  第 2 次请求回最终回答，恰 2 次请求）
- 另跑了一次可见演示：mock 提供商下 Aris 自主调用工具，工具返回带来源的片段，
  最终答出「NAS 的 IP 是 192.168.1.20，端口 5000」
- `uv run pytest`：**85 passed**；下一步 WebUI 上传（B3 二阶段）

### 2026-09-18：知识库首期实现完成（`knowledge/` 摄入 → 检索全链路）

- **合并**：`store/` 与方案定案已并入 `develop`（merge commit `273a0cf`），
  feature 分支 `feat/knowledge-base` 已删除；知识库实现在新分支 `feat/knowledge`
- 新增 `knowledge/` 模块：
  - `migrations.py`：两表迁移（owner=`knowledge`）——`knowledge_docs`（文档级，
    路径 / hash / mtime / 状态）+ `knowledge_chunks`（块级，`vector(384)`，**冗余
    source_path / title** 以便单表检索直接返回可引用信息）
  - `loaders.py`：md / txt / html 载入；**html 用 BeautifulSoup 自行转 markdown**
    （trafilatura 的 markdown 输出会把标题层级抹平，实测弃用），丢掉导航/页脚等噪声
  - `chunking.py`：标题层级切 + 定长兜底重叠（代码围栏内的 `#` 不算标题，
    超长段落按句子硬切，尾块过短并入前块）
  - `service.py`：摄入（**content hash 幂等 + 软删重建**）/ 列举 / 移除 /
    纯向量检索 / 建 HNSW 索引；总线服务 `knowledge.ingest|sources|remove|search|reindex`
- CLI 新增 `aris knowledge add|list|remove|search|reindex`；开关
  `config/knowledge.toml: enabled`；`store/` 补 `store.connect`（提供连接）与
  `store.embed_dimension` 两个总线服务，合计 10 个
- 修两处真实缺陷：① **迁移跑完即回滚**——psycopg 在已有隐式事务时
  `conn.transaction()` 会退化成 SAVEPOINT，故跟踪表建好后必须先 `commit()` 再逐条迁移
  （实测：迁移报成功但表不存在）；② `pg_ctl` 遇「残留进程占用共享内存」时，
  错误信息现直接给出 `pkill -f <pgdata>` 的处理提示
- 实测：`uv run pytest` **78 passed**（含端到端「摄入 → 幂等跳过 → 变更重建 →
  检索带来源 → 移除后查不到」）；CLI 冒烟摄入 `docs/developDoc/KNOWLEDGE-BASE.md` 得 23 块，
  检索「知识库的向量维度为什么选 384」命中 C1 段落，测试数据已清理
- **下一步**：agent 工具 `knowledge_search`（D1 定案：与 `web_search` 并列、
  由 Aris 自主调用）；之后是 WebUI 上传（B3 二阶段）

### 2026-09-18：store/ 迁移机制与向量检索 helper 完成（`store/` 地基收尾）

- `store/migrate.py`：自研轻量迁移——迁移以 Python 函数登记（按参数建表方便），
  记录表 `store_schema_migrations` 按 `(owner, version)` 唯一，**每条迁移单独事务**
  （PG 的 DDL 可回滚，失败不留半截 schema），**已应用的迁移改名即报错**（防 schema 漂移）；
  `store` / `knowledge` / `memory` 各自登记自己那一摊，互不干扰
- `store/vector.py`：pgvector 通用动作——建 HNSW 索引（cosine / l2 / 内积，可给
  m 与 ef_construction）、upsert（冲突键覆盖）、近邻检索（支持 `where` 过滤与
  `hnsw.ef_search`）、`count`、维度读取；**表名/列名/索引名一律校验后引用，算子与
  opclass 走白名单**，其余参数全部占位符
- 总线服务增至 **8 个**：`store.health` / `store.embed` / `store.migrate.run|pending` /
  `store.vector.search|upsert|ensure_index|dimension`；CLI 新增 `aris db migrate`
- 依赖新增 `pgvector>=0.5`（psycopg 适配器：连接时自动注册，缺失或未建扩展则降级）
- 实测：`uv run pytest` **67 passed**；临时表集成用例真跑通
  「建索引 → upsert → 余弦近邻 → where 过滤 → 维度读取」（DB 未运行时自动跳过）
- **`store/` 三块地基（PG 环境 / embedding / 迁移 + 检索 helper）已齐，
  下一步进 `knowledge/`**：先建表（migration）+ 分块，再做 CLI 摄入与检索

### 2026-09-18：store/ embedding 抽象跑通（本地 Bekko 384 维）

- 新增 `store/embedding/`：`base.py`（`EmbeddingProvider` Protocol + `EmbeddingError`）、
  `local.py`（本地 Bekko a25m，OpenVINO CPU，**懒加载** + 线程安全）、
  `__init__.py`（provider 单例注册）；`store/conf.py` + `config/store.toml`
  （provider / 模型 / batch / 截断维度）；总线服务 `store.embed`
- CLI：`aris store info`（配置 + 自检）/ `aris store embed <文本>`（打印维度与向量片段）
- 实测：`hotchpotch/bekko-embedding-v1-a25m` **384 维**编码通过；模型缓存落
  `data/models`（约 224MB）；`uv run pytest` **58 passed**
- **打包定案（取代 B/C 条目里「可选/独立环境」的口径）**：embedding 栈放
  **dependency-group `embedding`** 并加入 `[tool.uv] default-groups`——`uv sync` 一次
  装齐、`uv run` 不会把它卸掉（轻量环境用 `uv sync --no-default-groups`）
- 踩坑记录（已修）：① torch 与 torchvision 必须**同锁 PyTorch CPU 源**，否则
  torchvision 的 CUDA wheel 与 CPU torch 不匹配，报 `operator torchvision::nms does
  not exist`，`transformers` 直接导入失败；② OpenVINO 遥测往 `$HOME/intel` 写 consent
  文件，HOME 只读时会刷 warning（数据不外发，属无害噪音；已设 opt-out 环境变量，
  彻底消除需在可写 HOME 下跑一次或写 consent 文件）；③ HF 缓存经 `HF_HOME` 收进
  `data/models/`，不散落主目录
- 顺带修两处真实缺陷：① `is_running` 增 `pg_isready` 实测——崩溃后残留的
  `postmaster.pid` 会让 `pg_ctl status` **误报"运行中"**，进而 `aris db start` 拒绝
  启动（实测踩到）；② `bootstrap()` 更名 `bootstrap_env()`——函数与模块同名时被包内
  重导出遮蔽，`store.bootstrap` 拿到的是函数而非模块（已连踩两次）
- 内存实测：本地模型加载后进程峰值 RSS **约 1.2GB**，CLI 一次性命令退出即释放，
  无残留常驻（长驻服务会常驻该量级，属预期）
- 内存排查结论（2026-09-18）：Aris 自身**无常驻**（aris/python/postgres 进程数 0）；
  这轮 ~4GB 写入把 KDE **Baloo** 的 `baloo_file_extractor` 顶到 3.4GB（内容索引期间
  持续增长，杀掉后重启仍会再涨）。**已处置**：排除 `data/` 与 `~/.cache/`（备份
  `~/.config/baloofilerc.bak-20260918`）+ **关闭内容索引**
  （`balooctl6 config set contentIndexing no`）——extractor 不再启动，baloo 内存
  3.8GB → 130MB，`free` used 6.2Gi → 5.4Gi；文件名搜索不受影响，恢复用
  `set contentIndexing yes`。详见 AGENTS.md「开发环境」的本机注意
- 依赖新增（dependency-group）：sentence-transformers / `optimum[openvino]` / openvino /
  `transformers<5.1` / torch + torchvision（CPU）；`.venv` 约 1.5GB
- **下一步**：`store/` 的迁移机制与向量检索 helper，然后进 `knowledge/`

### 2026-09-18：store/ 环境地基跑通（`aris db` 可用）

- 新增 `store/` 模块：
  - `pgenv.py`：探针链（`ARIS_PG_BIN` → PATH 的 `pg_config` → `data/pg` → 未安装）
    + `PgEnv`（bin / pgdata / run / port / user / db）+ DSN 拼装（`ARIS_PG_DSN` 可整条覆盖）
  - `bootstrap.py`：micromamba（固定版本 + sha256 校验）→ conda-forge 装 postgresql +
    pgvector → `initdb`（UTF8、trust、仅监听 127.0.0.1）→ 启停 → 建库 →
    `CREATE EXTENSION vector` → 写 `data/pg/versions.txt`；全流程幂等
  - `db.py`：psycopg 连接与探活；对外总线服务 `store.health`
- CLI：`aris db init|start|stop|status|psql`（psql 后续参数原样透传）
- 实测：**PostgreSQL 17.11 + pgvector 0.8.1**；`data/pg` 约 166MB，另有包缓存
  `data/pg-pkgs` 约 91MB（可随时删）；首次下载实测约 **40MB**（原估 300MB 偏保守）；
  `uv run pytest` **51 passed**
- 踩坑记录（已修）：① `pg_ctl -o "-k <相对路径>"` 必然失败——postgres 启动后会
  chdir 到数据目录，故 `PgEnv` 内路径统一转绝对路径；② conda 默认把包缓存、元数据与
  `~/.conda/environments.txt` 写到主目录，已用 `MAMBA_ROOT_PREFIX` / `CONDA_PKGS_DIRS`
  / `XDG_CACHE_HOME` / `HOME` 全部收进 `data/`；③ `pg_ctl` 失败信息太少，已在
  `bootstrap.start()` 附带服务日志末尾
- 新增依赖 `psycopg[binary]`；文档同步（KNOWLEDGE-BASE 第 3.3 节改为 Python 实现并记录
  实测版本；AGENTS 模块划分 / 现状）
- **下一步**：`store/` 的 embedding 抽象（本地 Bekko，模型落 `data/models/`）、迁移机制
  与向量检索 helper

### 2026-09-18：议题 B（摄入侧）/ C（存储切分）定案 —— 知识库方案收尾

- **B 摄入侧**：来源 = 本地文件/目录 + HTML（`trafilatura` 已是既有依赖）；**不做**
  PDF、目录监听、从对话自动沉淀。**CLI 先行**（`aris knowledge add|list|remove|search`），
  WebUI 上传排第二；**agent 不给摄入权限**（只给检索，与「用户投喂资料」定位一致）。
  增量 = **content hash 幂等 + 软删重建**，两表 `knowledge_docs` / `knowledge_chunks`。
- **C 存储与切分**：**向量维度 384（本地 Bekko）**，不用云端——云端是 `memory/` 冷侧
  的事，且可避免 Cloudflare 断联降级逻辑。本地 embedding 属重依赖 → 可选/独立环境安装
  + `store/` 懒加载，未安装则知识库自动禁用；摄入串行限并发（压测下约 1164% CPU，
  避免打满主机）。分块 = 标题层级切 + 定长兜底重叠（保留 `heading_path`）；元数据
  11 字段 + `meta jsonb`；索引 HNSW + cosine（`m=16` / `ef_construction=64`），
  先导数据后建索引。
- **实现次序**：**`store/` 底层先行** → `knowledge/` → `memory/` 复用同一底层。
- **总线定名**：按职责核对 `core/bus.py`——含服务注册表（`provide`/`call`）+ 事件广播
  （`subscribe`/`emit`）+ 审计查询，故定名**「跨模块通讯总线」（CMCB）**；**暂不改名**
  （涉及既有 16 个服务命名与多处文档），留作待办。
- 知识库四个议题（A/B/C/D）**全部定案**；已同步 `AGENTS.md` 与
  `docs/developDoc/KNOWLEDGE-BASE.md`（第 4、5 节）。本轮仅文档，未写代码。
- **下一步**：进入实现——先做 `store/`（PG 环境 bootstrap → 连接池 → 迁移 →
  embedding provider → 建表 helper）。

### 2026-09-18：议题 A（边界归属）/ D（检索侧）定案

- **A 边界与归属**：新建两个顶层模块——
  - `store/`：embedding 抽象（文本 → 向量）+ PostgreSQL/pgvector 基础设施
    （DSN、连接池、迁移、向量检索 helper），**不认识** `memory/` / `knowledge/`
  - `knowledge/`：知识库业务（摄入、分块、来源管理、检索语义）
  - 依赖单向 `knowledge →（大总线）→ store`；`memory/` 后续复用 `store/`
  - **模型本体放 `data/models/`**，不进仓库
- **A3 不做 skill**：知识库属**内部底层设施**，能力经大总线暴露；skill 是外部扩展
  接口，内部模块绕经它只增一层壳与延迟。启用开关 `config/knowledge.toml: enabled`。
- **D 检索侧**：agent 工具**自主调用**（与 `web_search` 并列，不做每轮自动注入）；
  第一阶段**纯向量**（混合检索 / rerank 列第二阶段）；结果格式沿用 web_search 约定
  且**必带来源标识**（路径 + 标题 + 位置）；与记忆检索**两条独立通路**，不合并入口。
- 总线服务（实施时落表）：`store.embed` / `store.health` / `store.migrate` /
  `knowledge.search` / `knowledge.ingest` / `knowledge.sources`。
- **新增待定**：用户计划给总线重新取名，届时统一调整既有 16 个服务命名。
- 已同步 `AGENTS.md`（模块划分 / 已定案 / 待定 / 开发路线）；详
  `docs/developDoc/KNOWLEDGE-BASE.md` 第 4 节。本轮仅文档。
- **下一步**：议题 B（摄入侧）/ C（存储切分）。

### 2026-09-18：数据库部署方案定案（前置阻塞解除）

- **结论**：数据库环境**不依赖系统安装**，由项目脚本按需自动获取便携实例，
  目标「clone 下来就能用」。定案 **micromamba + conda-forge**（`postgresql` +
  `pgvector` 同源，免 root、免编译、装到 `data/pg/`，`.gitignore` 已覆盖）。
- 排除 EDB 官方 binaries tarball（实测 403，改走许可跳转，且不含 pgvector），
  也排除二进制入仓（体积 200MB+，违反「数据不进 git」）。
- 探针链：`ARIS_PG_BIN` → PATH 中 `pg_config`/`postgres` → `data/pg/` → 下载。
  代码只认 DSN，不感知实例来源 → 该决策不影响议题 A/B/C/D。
- **pgvector 取预编译包、不源码编译**：读源码确认 pgvector 在 glibc Linux 上自动启用
  `USE_TARGET_CLONES`（运行期选 FMA 快路径）；本机 Xeon E5-2673 v3 无 AVX-512，
  `-march=native` 无额外收益。
- 已同步 `AGENTS.md`「已定案」；详 `docs/developDoc/KNOWLEDGE-BASE.md` 第 3 节。
- 未写代码，仅文档；下一步进议题 A（边界与归属）/ D（检索侧接口）。

### 2026-09-14：知识库进入准备阶段（商讨中，未定案）

- 用户决定启动**知识库**能力建设，定位为**面向外部资料的独立 RAG 知识检索
  能力**，与 Aris 个人记忆分开。
- 已开分支 `feat/knowledge-base`（从 `develop` @ `7f0b4dd` 拉取）。
- 新建 `docs/developDoc/KNOWLEDGE-BASE.md`（**商讨稿**）：登记定位、可沿用的既有
  地基、前置阻塞、待商讨决策点（A 边界归属 / B 摄入侧 / C 存储切分 / D 检索侧）。
- **尚未定案**：知识库与 `memory/`（记忆系统主线）的边界与先后次序均待商讨；
  本轮只做准备，未写代码。
- **前置阻塞（实机探测）**：本机 PostgreSQL / pgvector / docker / podman 均不存在，
  数据库环境搭建方式待定。

### 2026-08-30：版本 v0.3.1（WebUI 安全审查 + 总线化改造 + 防复发机制收官）

- 版本号三源同步 bump 至 **v0.3.1**（patch 级：本轮为修复/重构/工具，无新功能）。
- 全部阶段合并回 develop，`uv run pytest` 48 通过，`scripts/release-check.sh` PASS。
- 详细条目见下方「2026-08-30：WebUI 安全审查 + 总线化改造 + 防复发机制」。

> 遗留待办（2026-08-23 记）：仪表盘系统状态区域、htmx（可选）、Lucide 图标（可选）。

### 2026-08-30：WebUI 安全审查 + 总线化改造 + 防复发机制

**背景：** 接手被部分废弃的 v0.3.0 WebUI 代码，按用户决策顺序收尾：
修复安全/规范问题 → 总线化 → 补测试 → 流程防复发 → 回归记忆系统主线。

**安全修复（已合并回 develop）：**
- 路径穿越：技能删除/日志读取/配置模块参数/技能名 `..` 均可越界读写 → 全部根治
- TOML 注入：providers 改 tomli_w 结构化写回；config 手写 toml 补全转义 + 键白名单
- XSS：marked.js 输出经 DOMPurify 净化；SSE `innerHTML` 注入 → 事件流改 `tojson`+文本节点
- 鉴权绕过：`/login` 前缀宽匹配（`/loginfoo` 可绕过）→ 精确集合 + 前缀分离
- 业务缺陷：审计页时间戳全显当前时间、分页失效 → 修正（`AuditRecord.wall_ts`）
- 静默吞异常 → 记 loguru warning；provider 重定向错误 URL 拼接修复
- 技能目录从 CWD 相对路径改为包内绝对路径 `SKILLS_DIR`

**总线化改造（严格 core.call，已合并）：**
- 新增 16 个总线服务：`llm.providers.*`（manage.py）/ `llm.fetch.*`+`llm.retired.*`
  （fetch.py）/ `skills.*`（manager.py）/ `audit.recent`+`audit.summary`（bus.py）
- webui 全部 9 个路由改走 `core.call`，消灭对 core.llm/core.audit/behavior.skills 直连
- `create_app()` 触发注册 + `_verify_bus_services()` 启动自检（`bus.has_service`）
- 基础设施例外（记入 BUS-ARCHITECTURE.md）：`get_settings` / `cfgtoml` 直连不算模块间通讯

**测试与防复发：**
- 新增 tests/test_webui.py 11 用例：auth / 限流 / config 写回 / skills CRUD 全链路，
  全部隔离到 tmp_path；`uv run pytest` **48 passed**
- `.githooks/pre-commit`：main 禁非合并提交、develop 直提警告（三场景已实测）
- `scripts/release-check.sh`：版本三源一致 + develop 分支 + 无未合并分支检查
- AGENTS.md / BUS-ARCHITECTURE.md / SECURITY-AND-REFACTOR-PLAN.md 已同步

**偏差存档（用户决策）：**
- 历史提交（v0.2.6/v0.3.0 默认 merge message、WebUI 直落 develop）**保持原样不重写**
- `config.toml.read/write` 未走总线（属配置系统基础设施，记为明文例外）
- 审计查询跳过总线与否由 `audit.*` 服务统一封装，路由不感知

**下一步：** 回归主线——记忆系统（PostgreSQL + pgvector）。

### 2026-08-23：WebUI 管理后台完成（v0.3.0）

**已完成：**
- FastAPI 应用工厂 + 路由注册
- 登录鉴权（HMAC cookie + 限流 5次/5分钟）
- 仪表盘（统计卡片 + 快捷入口）
- 审计流水（表格展示 + 筛选 + 分页 + SSE 实时流）
- 提供商管理（列表 + 模型详情 + 增删 + fetch 审核 + 退休管理）
- 技能管理（列表 + 详情 + 创建/编辑/删除 + marked.js 渲染）
- 配置管理（表单编辑 toml + .env 只读 + 保存前备份）
- 日志查看（文件浏览 + 分页 + SSE 实时流）
- 对话历史（占位页）
- 响应式布局
- 请求日志中间件

**新增依赖：**
- fastapi / uvicorn / jinja2 / python-multipart

**待完成（记录待办）：**
- 仪表盘系统状态区域
- htmx 引入（可选）
- Lucide 图标（可选）

