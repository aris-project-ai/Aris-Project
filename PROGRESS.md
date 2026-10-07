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
| `character/` | 提示词工程版（单一 `character.system_prompt`）；多人格见 BACKLOG #4 |
| `webui/` | 完成：鉴权 / 仪表盘 / 审计 / 提供商 / 技能 / 配置 / 日志 / 知识库页 |
| `serve/` | **完成（v0.4.1）**：`aris serve` 一条命令起全套（缺则自建 PG、自启、预热 embedding、并入 WebUI），`--only/--skip/--dry-run` 可裁剪 |
| `store/` | 完成：便携 PG 17.11 + pgvector 0.8.1、embedding（本地 Bekko 384 维）、迁移 + 向量 helper；**可迁移性（v1.0 M0）**：二进制可运行验证 + 重获取、属主可操作报错、角色探测对齐、端口自动避让 |
| `knowledge/` | 首期完成：两表 / 分块 / 摄入 / 纯向量检索 / CLI / agent 工具 / WebUI 页 |
| `memory/` | **设计已定案（2026-09-29）**：内容模型见 `docs/developDoc/MEMORY.md`（分层 / 事件 / 两周记 / 惰性衰减 / 注入 / 表结构）；会话与消息表见 D2。**D16 = A 级，8 条待商讨已补完** |
| `voice/` | **占位**（选型见 `docs/developDoc/stt&&tts选型.md`） |
| `autorun/` | **方向已定，暂不实现（2026-09-28）**：纯调度器 + 触发源抽象（D11） |

- **入口**：`aris serve` 一条命令即可（首次自动获取便携 PG，需联网数分钟）；
  `aris doctor` 体检、`aris chat` 终端对话（调试用，与应用互不干涉）
- 测试：`uv run pytest` **103 passed**（DB 未运行则集成用例自动 skip）
- 数据库：便携实例在 `data/pg`，项目本地、不注册系统服务；`aris serve` 会按需自建/自启，
  退出时只停自己拉起的那个
- 知识库现有资料：`data/knowledge/刑法.md`（约 129 块）
- 待办方向：`docs/developDoc/BACKLOG.md`（8 条中长期，**2026-09-28 已全部过一轮商讨**）
- 已知陷阱（踩坑档案，修完就补）：`AGENTS.md`「已知陷阱」节

## 最近动态

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
> **M1 进行中**（serve 上收 / 组装根）。

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
