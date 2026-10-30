# AGENTS.md

> 本文件是 Aris 的最高权威与通用规则：**读完本文件 + 对应模块文档，就能开始开发**。
> 为了方便称呼以及区分开发者与用户，本文档中可能会使用dever来称呼开发者（通常为莫琳）。
>
> 这些规矩绝大多数是踩坑踩出来的。写下来不是为了管住谁，是为了下次别再踩同一个坑。

## 1. 权威与规则

- **最终权威归开发者，尤其是莫琳。**
- 冲突时的取用顺序：**AGENTS.md > `docs/forAiDoc/` 各专文档 > `PROGRESS.md` / `todolist.md`
  > `docs/archive/`**。都不合，停下来问开发者，不要自己拍板。
- **待办唯一真相源是仓库根 `todolist.md`**：要做的事只写在那里，按阶段推进；
  旧的 `BACKLOG.md` 已归档作废。**事实优先于文档**——能用 CLI / 代码常量表达的事实，
  不再单独写进文档。
- **准入标准**：AGENTS.md 只收两类内容——**通用规则**（适用于所有模块）与**最高权威判定**。
  单模块实现细节、一次性决定、历史过程都不进来。
- **职责不重复原则**：一个事实只在一个地方写完整。
  - 写之前先找：已有权威位置就**只加指针**，不抄一份；
  - 已有重复的，**只留一处**（留在最适合它的位置），其余删掉或改成指针；
  - 现有内容位置不对就**迁移**过去，不要复制后留下两份。
- **指针是选择性的**：细节量大、只在特定场景才需要的内容留指针；超出本文件职责、
  但对开发明显有利的内容（关键约束、易踩的坑）直接写在这里。
- **面向未来（i18n 远景）**：将来可能做多语言，现在不引框架、不做翻译，但**新增用户可见文案
  不要硬编码在业务逻辑里**（集中到常量 / 资源处），避免到时候满地改。
- **两份文件不要乱动**：`README.md` 面向使用者（简介 + 快速开始），
  `docs/forAiDoc/Aris-Project.md` 是全项目的信念与蓝图（定位与大致形态）。改这两份要先
  得到开发者同意；日常开发只在确有必要时补一句，不要重写、不要把它们当索引用（索引由本文件负责）。
- **必须读进度**：每次开工前先读 `PROGRESS.md`，确认当前版本、模块状态与阻塞；
  不要凭记忆或聊天记录判断项目状态。读完再按 §10 取对应模块文档。
- **不擅自删不认识的改动**：看到不理解的代码、文档、未提交改动，先问，不要当垃圾清掉。
- 对话中称「开发者」；明确是莫琳时可直接称名字；**不要用「dever」称呼对方**。

## 2. 会话启动与常用命令

- 先执行 `fastfetch` 确认环境；`fastfetch` 不可用则用 `uname -a` / `/etc/os-release` 判断；
- **安卓端（Termux）**：**尽量只做文档改动**，不跑代码、不装包、不做 git 操作；
  只要任意一条命令能正常返回就视为 bash 可用（含 git）；文件操作优先用 read / write / edit / glob，
  glob 偶发失败时改用 read 读目录。
- 动手前读 `PROGRESS.md`（硬要求，见 §1），再按 §10 的文档路由读对应模块文档。

### 常用命令

一律用 `uv run`，不要直接调 `.venv/bin/python`。

| 命令 | 用途 |
|---|---|
| `uv run aris serve [--only/--skip/--dry-run]` | 一条命令起全套（PG 自启、迁移、embedding 预热、WebUI） |
| `uv run aris doctor` | 环境与依赖自检；出问题先跑它 |
| `uv run aris chat` | TUI 调试对话（不自启数据库） |
| `uv run aris web` | 只起 WebUI |
| `uv run aris db init\|start\|stop\|status\|migrate\|psql` | 便携库管理；`psql` 直接进库看数据 |
| `uv run aris knowledge add\|list\|remove\|search\|reindex` | 知识库摄入与检索 |
| `uv run aris llm list\|check\|test\|fetch\|missing` | 提供方与模型管理 / 缺失记录（只读） |
| `uv run aris store info\|embed` | embedding 自检 / 试算 |
| `uv run pytest [-q] [tests/test_x.py]` | 测试 |
| `bash scripts/check.sh` | 本地全检：ruff check / format + mypy + pytest（提交前跑） |

**CLI 功能必须 ≥ WebUI**：WebUI 有的能力，CLI 必须先有（只能多不能少）；新增 WebUI 功能前先补对应命令。
通常情况下，能使用CLI也就意味着能使用终端工具，因此如改设置这类功能可以通过vim/nano/sed......实现，不需要在cli额外添加实现

## 3. 项目

Aris 是一个**基于大语言模型、类似 Neuro-sama 的赛博生命体**。目标不是做助手，
而是长期独立的人格、持续演进的世界观、人际关系网与成长轨迹。

- **交互以语音为主**（STT → LLM → TTS），文字为辅，并接入外部平台（Matrix / Discord 等）。
  TUI（`aris chat`）只是开发调试入口，WebUI 是运维管理后台，两者都不是最终对话界面。
- **单进程多会话**，每个角色一个当前会话；记忆与历史按角色（`cid`）分区。
- **多人格 = 多个人**：各自会话、各自记忆，互相是不同的人；**不做人格分裂**。
- **跑起来**：`uv sync` → `uv run aris serve`。首次启动会播种 `data/config/`、自动获取便携
  PostgreSQL（需联网数分钟），WebUI 在 `http://127.0.0.1:9690`。
- 纯个人项目，但**可维护性是最高优先级**，目标运行数年。
- **许可证**：AGPL-3.0-or-later，全文见 `COPYING`；打包元数据以此为准。
- **开发节奏**：先跑通核心链路（STT → LLM → TTS），再逐层叠加能力；基础架构方向提前定，
  功能随后逐步完善。

## 4. 目录地图

| 路径 | 职责 |
|---|---|
| `src/aris/core/` | CMCB 总线（服务注册 + 事件 + 审计）、LLM 提供方抽象（fallback / 流式 / 工具调用） |
| `src/aris/store/` | 存储基础设施：便携 PG + pgvector、embedding 抽象、迁移机制、向量检索 helper；不认识业务语义 |
| `src/aris/knowledge/` | 知识库：外部资料的 RAG（摄入 / 分块 / 检索），384 维本地 embedding；不做 skill，只经总线暴露；摄入走 CLI，agent 只给检索工具 |
| `src/aris/mcp/` | 通用 MCP 客户端：官方 `mcp` SDK + `data/config/mcp.toml` 驱动 transport；owner 线程 asyncio，同步总线服务（见 `docs/forAiDoc/MCP.md`） |
| `src/aris/memory/` | Aris 的个人记忆。**暂停开发**，重启时间由开发者决定；详见 `docs/forAiDoc/MEMORY.md` |
| `src/aris/character/` | 角色载体：`data/characters/<cid>/`（`character.toml` + 世界观 / 关系 / 成长占位）；`cid` 创建时生成（uuid），改名 / 改人设不影响 |
| `src/aris/behavior/` | 行为：工具注册表（含世代同步）、agent loop、内置工具、skills 系统；联网搜索是**引擎池**（`behavior/search/`：Bing 直连 / Tavily 含 keyless / Exa 经 mcp，见 `docs/forAiDoc/WEB-SEARCH.md`） |
| `src/aris/chat/` | 文字对话 + TUI（`aris chat`，开发调试用） |
| `src/aris/serve/` | 启动编排：唯一组装根，按序拉起各模块；单向、非守护、不含 TUI，不对外提供查询服务；**任何模块不得 import serve**（serve 是启动器，不是库；运行时对象归 `behavior/runtime.py`） |
| `src/aris/webui/` | 管理后台：鉴权 / 仪表盘 / 审计 / 提供商 / 技能 / 配置 / 日志 / 知识库 |
| `src/aris/voice/` | STT / TTS：TTS 已定 Edge TTS 起步（Azure 备选），STT 选型未定 |
| `src/aris/autorun/` | 定时与主动任务（只留设计，暂不实现） |
| `src/aris/seed/config/` | 随包配置模板：首次启动幂等播种到 `data/config/`（只补缺失，不覆盖用户改动） |
| `data/` | 运行时数据：`config/`（含密钥）`pgdata/` `state/` `knowledge/` `characters/` `skills/` `autorun/` `logs/` `models/` `pg/`（不进 git） |
| `docs/forAiDoc/` | 设计与契约文档（为什么这么设计、接口是什么） |
| `docs/archive/` | 历史存档（已作废的规则与方案），只读 |

## 5. 编码规范

- **语言**：变量 / 函数 / 类名一律英文；注释与 docstring 一律中文。
- **Python**：最低 3.12，开发按 3.14，尽量用新特性；包名 `aris`，src 布局，依赖用 uv 管理。
- **类型标注**尽量全，公开函数 / 类必须完整。
- **行宽**：**代码**限 100 列；**文档不限宽**。
- **格式与静态检查**：`ruff format` + `ruff check`（行宽 100，规则见 `pyproject.toml`）；
  `mypy` 渐进推进，当前只查 `src/aris/core` 与 `src/aris/store`。
- **行尾 / 缩进**：由 `.editorconfig`、`.gitattributes` 统一（LF、UTF-8）。
- **C 代码**：clang-format（仓库根 `.clang-format`，行宽 100）。命名：函数大驼峰（`ArisDemoAdd`）、
  变量小驼峰（`userCount`）、指针星号靠变量（`int *p`）、常量宏 UPPER_SNAKE_CASE。
  `src/aris/csrc/` 保留为 C 扩展示范（demo），真实性能热点再按需加入，**不要删**。
- **注释**：简单代码不写废话；复杂算法、业务逻辑、易误解处写清楚。
- **KISS**：一个东西只做一件事，每处职责单一；不写聪明的花活。
- **YAGNI**：不为不存在的需求设计，但基础架构方向要提前明确。
- **轮子哲学**：小功能自己写；重活（数据库、语音、LLM SDK）用成熟库。
- **重构态度**：核心 / 基础模块尽早重构；外围模块记账延后。能跑就不动，除非它开始阻碍开发或影响正确性。
- **技术栈（已定，勿自行更改）**：Python 为主、C 辅助（性能敏感处）、必要时 TypeScript；
  pydantic-settings 配配置；loguru 记日志；pytest 写测试；ruff + mypy 做静态检查。
- **加依赖**：用 `uv add`；重依赖进 dependency-group `embedding`（默认安装，
  `uv sync --no-default-groups` 可要轻量环境）。
- **对外文案**：项目显示名与仓库地址只在 `src/aris/branding.py` 定义（模板经渲染上下文取
  `app_name` / `github_url`），新增用户可见文案同样收成常量。**代码标识不随品牌改名**：
  `import aris`、命令 `aris`、`ARIS_` 前缀、数据目录名保持稳定。

## 6. 架构约束

### CMCB（跨模块通讯总线）

- **定位**：`src/aris/core/bus.py` 一处承载三件事——服务注册表、事件广播、审计。
  全项目的模块间通讯都走它，模块之间不互相 import。
- **服务面**：`provide(name, fn)` 注册、`call(name, ...)` 调用（同步、可有返回值）、
  `has_service(name)` 探测、`services()` 列出。服务名 `module.service`，事件名 `module.event`；
  前缀是模块名，代码标识符不带 `aris`。
- **注册方式**：核心类在自己的 `__init__` 里 `provide` 自己的方法（实例自注册），
  模块 `__init__.py` 里完成登记；不另建注册中心。
- **缺失与异常**：`call` 遇到未注册的服务会记 error 日志 + 给出最相近的服务名建议，
  **返回 `None`**（宽容降级）；被调函数抛异常则审计记 `ok=False` 后**原样抛出**。
  因此调用方拿到 `None` 时要按「服务不可用」处理，不能直接属性访问。
- **事件**：`emit(event, payload)` / `subscribe(event, handler)`，同步执行；
  无订阅者时静默丢弃，单个订阅者异常不影响其他订阅者。
- **审计**：每次 `call` / `emit` 记一条流水（`audit.recent` / `audit.summary` 本身也是总线服务），
  审计失败不影响业务调用。
- **不走总线的边界**：对象构造 / 依赖注入、同模块内部调用、纯类型引用（如 `Message`）、CLI 组装根。
- **serve 是启动器，不是库**：任何模块不得 import `serve`（`cli.py` 入口与测试除外）；运行期单例（engine / registry / runtime）归 `behavior/runtime.py`。
- **依赖声明与核验**：各模块声明自己的 `REQUIRED_SERVICES`，由 `serve` 的 `services` 步骤
  （required）统一核验；`serve.assemble()` 是**唯一**的 import 触发点，别在别处 import 所有者模块。
- **改服务时**：新增 / 改名 / 删除要同步 `docs/forAiDoc/CMCB.md` 的服务表，并全仓搜索调用点。
- 服务表与架构详见 `docs/forAiDoc/CMCB.md`。

### 依赖与错误处理

- 依赖方向单向：`memory` / `knowledge` → 总线 → `store`，不许反向依赖。
- 核心逻辑快速失败、不留脏状态；外围功能宽容降级，但**降级必须记日志**，禁止静默失败。

### 单一会话

- Aris 只有一个当前会话（**每角色一个**）；**不做、也不允许子代理**；
  一切输入无论来自 TUI、语音还是 SNS，都进入同一个会话。
- 会话复用最近一段（冷却上限默认 5 天，可配，拉长是为了吃 API 的 KV cache 省钱），根据DeepSeek文档所述，建议改为一天。
- 并发输入**串行排队**，不并行改历史。
- compact 摘要、记忆提取这类**同一会话的内部维护动作**不算子代理。

### 配置

配置只有一处：`data/config/`（路径由 `src/aris/paths.py` 决定）。缺失时回落到随包种子模板
`src/aris/seed/config/`——首次启动幂等播种（只补缺失、不覆盖用户改动；secrets 置 0600）。

| 文件 | 管什么 | 读取方式 |
|---|---|---|
| `data/config/settings.toml` | 启动级参数（`[settings]` 表，非密钥） | 键映射成 `ARIS_<KEY>`，再由 pydantic-settings 读（`src/aris/config.py`） |
| `data/config/secrets.toml` | 密钥：键名就是环境变量名（`DEEPSEEK_API_KEY` 等） | `setdefault` 进 `os.environ`（`src/aris/config.py`） |
| `data/config/providers.toml` | LLM 提供方：base_url、key 环境变量名、超时、transport、模型 | `src/aris/core/llm/config.py`；`ARIS_LLM_PROVIDERS_FILE` 可覆盖路径 |
| `data/config/<module>.toml` | 各模块可调参数（chat / search / logging / serve / knowledge / mcp / store / webui / audit / notify） | `src/aris/cfgtoml.py` |
| `data/config/modules.toml` | 模块开关（`[modules]`） | `aris modules` / serve 装配 |

- 优先级：代码内 dataclass 默认值 < 种子模板 < `data/config/*.toml` < 进程环境变量。
  缺文件、缺键、解析失败都静默用默认值（记 warning，不抛异常）。
- `data_dir` 不写进 TOML：只认进程环境变量 `ARIS_DATA_DIR`（否则鸡生蛋）。
- 收口原则：枚举 = 代码内 StrEnum；实现细节 = 模块顶部常量；真正可调的才进 toml；
  密钥永远只在 `data/config/secrets.toml`（其他 toml 只写 key 的环境变量名）。
- 不再有 `.env`：配置一律 TOML；临时覆盖用进程环境变量。
- 详见 `docs/forAiDoc/CONFIG.md`。

### 可迁移性与启动幂等

换机 = 新机 `git clone` → 把原机 `data/` 全量拷过来 → `uv run aris serve` 直接起。

- 不写死绝对路径；**不把「已验证状态」存进库**，一切启动时重新探测。
- 启动必须幂等：缺什么补什么，重复执行无副作用。
- 端口与角色名**不写进配置文件**（端口运行期分配，角色名新建集群统一 `aris`）。
- `data/` 分层：**必须带** `config/` `pgdata/` `knowledge/` `characters/` `skills/` `autorun/`；
  **可重建** `pg/` `bin/` `models/` `logs/` `state/`；`.venv/` 不在 `data/`。

### 数据与密钥

- 运行时数据（配置、密钥、日志、数据库文件）统一放 `data/`，**不进 git**。
- `data/pgdata/` 是全部业务数据（记忆、知识库都在库里），**不要手删**；要重置先问开发者。
- 密钥（API key）一律放 `data/config/secrets.toml`（0600，播种时自动设置），**不进 git**；
  进程环境变量优先，可临时覆盖。
- 日志：`data/logs/YYYY-MM-DD/aris.log`；级别 `ARIS_LOG_LEVEL`，轮转与保留见 `data/config/logging.toml`。
- 备份：`rsync -av data/ /backup/aris-data/`；数据库在跑时用 `pg_dump` 更稳。

### 常见改动落在哪

| 要加 / 改 | 动哪里 |
|---|---|
| 新的跨模块能力 | 在模块 `__init__` 里 `provide` 服务 + 同步 `CMCB.md` 服务表 |
| 新的内置工具 | `behavior/tools/<name>.py`（提供 `register(registry)`）+ 在 `tools/__init__.py` 汇总注册 |
| 业务模块的 agent 工具 | 壳声明在**能力归属模块**：模块内 `tools.py` 构造 `ToolSpec`（`core/tools.py`），`__init__.py` 里 `provide("<模块>.ai_tools", tool_specs)`；behavior 装配时探询收编，behavior / serve 零改动。工具 fn 不 provide 成总线服务。**文案不做人味**（不拟人、无第一人称）：只有 HTTP 报错给映射成「限流 / 鉴权失败」等人话 |
| 新的数据库表 | `store/migrate.py` 的 `register([Migration(...)])`：owner 内 version 递增，历史迁移不许改写 |
| 新的可调参数 | 模块 dataclass 默认值 + `data/config/<module>.toml`（模板进 `src/aris/seed/config/`）+ `CONFIG.md`；密钥不进来 |
| 新的 CLI 子命令 | `cli.py` 的 subparsers（含 `-h` 文案） |
| 新的模块 | `serve/__init__.py` 的 `assemble()` 加 import + `serve/steps.py` 加步骤 + 声明 `REQUIRED_SERVICES` |
| WebUI 页面 | `webui/routes/` + `webui/templates/` + `webui/static/`；路由一律走 `core.call` |

## 7. 验证

- 改动可能影响运行时，**必须实际运行验证**。
- **提交前**跑 `bash scripts/check.sh`（ruff check / format + mypy + pytest）；涉及业务逻辑的改动
  至少跑它，确认无回归。
- 纯文档改动不需要跑测试。
- **开发闭环**：改代码 → 跑测试 / 起服务实测 → 更新文档（契约变化写模块文档，状态变化写
  `PROGRESS.md`）→ 提交。
- **测试细节**：用例在 `tests/`；`tests/support/` 提供 mock LLM / mock HTTP；
  `conftest.py` 会调用 `serve.assemble()` 注册全部服务。依赖真库的用例在 PG 未运行时自动 skip，
  跑全量前先 `aris db start`。单跑一个文件：`uv run pytest tests/test_xxx.py -q`。

## 8. Git 流程

- **`develop` 是日常汇聚分支**：所有开发先开 feature 分支（`feat/` `fix/` `docs/` `refactor/` 前缀，
  从最新 develop 拉出），分支内小步提交，验证后 `git merge --no-ff` 合并回 develop，
  随后删除本地与远程 feature 分支。日常开发不直接碰 main。
- **`main` 只进发布**：beta 版与正式版发布时从 develop 合并回 main（`--no-ff`）并打 tag。
- `oldWish` 是历史保留分支，不要删除。
- **提交信息**：`<type>(<scope>): 简短中文描述`，type 取
  `feat|fix|docs|refactor|chore|test|build|ci|perf|style|revert`。
- **body**：空行后**用 `-` 分条**列出改了什么，每条一两句，必要时简述原因；
  不要写成技术文档长文（踩坑与背景记进本文件陷阱节或 `PROGRESS.md`）。
- **一次提交只做一件事**（代码与文档分开）；同一文件的改动一次改完。
- 版本号攒到**阶段性发布**再 bump，不要为了「有进展」频繁 bump。
- 仓库自带 commit-msg 与 pre-commit hook（提交格式 + 分支保护 + staged Python 的 ruff 检查），
  换机后先跑 `bash scripts/install-git-hooks.sh`。
- 纯格式化提交记录在 `.git-blame-ignore-revs`；首次 clone 建议
  `git config blame.ignoreRevsFile .git-blame-ignore-revs`。

## 9. 版本号

- **唯一源**：`src/aris/__init__.py` 的 `__version__`。`pyproject.toml` 走 `dynamic = ["version"]`，
  `uv.lock` 不记录本项目版本；`[tool.uv] cache-keys` 必须含该文件（否则改了版本 uv 不重建元数据）。
- **版本串只写数字**：`X.Y.Z` 或 `X.Y.Z.W`，不带 `.dev0` / `-beta` 等后缀；渠道只由 tag 表达。
- 当前两类渠道，**都发布在 main**：

| 渠道 | tag | `__version__` |
|---|---|---|
| beta（小版本更新） | `beta-vX.Y.Z` | `X.Y.Z` |
| 正式版 | `vX.Y.Z` | `X.Y.Z` |

- **号码全线唯一**：beta 与正式共用一条数字线，同一个 `X.Y.Z` 只能出现一次；
  有 `beta-v1.0.1` 就没有 `v1.0.1`，反之亦然；要发另一个渠道就用更高的号。
- beta 不是预发布，只是小版本更新标记；不靠版本串排序区分渠道。
- **密集发布、单个 patch 装不下的小功能**可下探一段：`vX.Y.Z.W`（beta 线写 `beta-vX.Y.Z.W`）。
- **alpha 渠道**：只在 `develop` 发布，tag 形如 `alpha-vX.Y.Z`，用于 v1.0.0 前的预发布；
  **占用数字线**（与 beta / 正式同规则，同号不得再发其他渠道）。
- **大版本代号**：v1.0.0 = **「跨越」（Cross）**。代号只写在本节与发版说明里，不散落到文档各处。
- 改版本用 `bash scripts/bump-version.sh <版本|patch|minor|major>`：校验干净 develop、
  号码未被占用、版本递增，改源 + `uv lock` + `uv sync`，**只改文件不提交**。
- 发版前必跑 `bash scripts/release-check.sh`：号码已被任一渠道占用就 FAIL。
- 历史 tag（如 `v0.4.2-beta`）保留不动；新规则从下一次 bump 起生效。

## 10. 文档路由

| 要做的事 | 先读 |
|---|---|
| LLM 接入 / `core` 模块 | `docs/forAiDoc/API-CALL.md` |
| 跨模块通讯总线 CMCB | `docs/forAiDoc/CMCB.md` |
| 配置体系 | `docs/forAiDoc/CONFIG.md` |
| 启动编排 `serve/` | `docs/forAiDoc/SERVE.md` |
| 记忆系统（暂停） | `docs/forAiDoc/MEMORY.md` |
| 知识库 | `docs/forAiDoc/KNOWLEDGE-BASE.md` |
| 通用 MCP 客户端 | `docs/forAiDoc/MCP.md` |
| 技能系统 | `docs/forAiDoc/SKILLS.md` |
| 提供商 / 模型管理 | `docs/forAiDoc/LLM-PROVIDER-MGMT.md` |
| WebUI 管理后台 | `docs/forAiDoc/WEBUI.md` |
| 可迁移性 / 单一会话 | `docs/forAiDoc/PORTABILITY-AND-SINGLE-SESSION.md` |
| v1.0 施工方案与验收 | `docs/forAiDoc/V1.0-PLAN.md` |
| 当前状态与下一步 | `PROGRESS.md` |
| 待办与阶段计划（唯一真相源） | `todolist.md` |
| 当前阶段施工文档（过程性） | `docs/process/v0.4.4.md` |
| 已作废的旧待办（只读） | `docs/archive/BACKLOG-2026-10.md` |
| 项目蓝图 / 参考材料 | `docs/forAiDoc/Aris-Project.md`、`docs/referenceDocumentation/` |
| embedding（`store/` 侧） | `docs/forAiDoc/EMBEDDING.md` |
| 插件系统 / 文档站（均搁置） | `docs/forAiDoc/PLUGIN.md`、`docs/forAiDoc/DOCS-SITE.md` |
| 安全审查与总线化改造记录 | `docs/forAiDoc/SECURITY-AND-REFACTOR-PLAN.md` |
| TUI 已知问题 | `docs/forAiDoc/TUI-问题修复.md` |
| 旧事 / 已作废的方案 | `docs/archive/` |

### 文档规范（`docs/forAiDoc/`）

**分层**：AGENTS 是规则与唯一索引；`docs/forAiDoc/` 只收**契约与约束**（边界、接口、为什么这么设计、坑、未决）；
`docs/` 放人类文档（如 `DEV-FLOW.md`）；`docs/process/` 放阶段施工文档（过程性，阶段结束后移入 archive）；
`docs/referenceDocumentation/` 是外部资料快照（已基本废弃，暂不维护）；
`docs/archive/` 只读。**状态进 `PROGRESS.md`，待办进 `todolist.md`，过程进 archive。**
本规范只适用于AI， `docs/forAiDoc` 从目录名也可以看出只适用于AI，对于人，文档现阶段放在 `docs/` 根目录。
人类开发者不受本文档以及其他针对AI的文档的约束。对于人，规范将在后续完善。

**准入（硬规则）**：

1. **能从代码或 CLI 得到的事实不写文档**——模块 / 开关看 `aris modules list`，服务看 `aris services list`，
   工具看 `aris tools list`，配置看 `aris config list|show`，路径与版本看 `aris info`，健康看 `aris doctor`。
   文档不再抄这些表与清单。
2. 历史、进度、待办、过程不进 forAiDoc。
3. 一个事实只写一处；其余只留指针。
4. **不写行号、文件名清单、函数名清单、服务表、配置项表**——这些必然漂移；引用符号名或命令。

**每份文档固定开头**：

```
# <主题>
> 状态：契约 | 暂停 | 搁置
> 代码入口：src/aris/<module>/
> 事实查看：aris <command>
```

**其它**：正文不写日期（外部资料快照在头部标抓取年月）；不设行数上限，但写长了先自查是否重复或该拆；
**未开工的设计不进 forAiDoc**（归档，开工时按 `todolist.md` 重写）；`MEMORY.md` 由开发者本人维护。

## 11. 已知陷阱

一句话一条，只写结论；来龙去脉在 `docs/archive/`。

### 数据库 / 迁移

- 迁移「报成功但表不存在」：建跟踪表后必须先 `commit()`，再逐条跑迁移。
- **便携 PG 是项目本地的**：不注册系统服务、不随开机自启；用 WebUI / 对话前先 `aris serve`
  （或 `aris db start`）把它拉起来。
- `pg_isready` 退出码 `1` 也可能是「在跑但拒绝本次探测」，只有 `2` 才算停。
- 残留 `postmaster.pid` 与 run 目录里的 `.s.PGSQL.*`（含 `.lock`）都会挡住启动，两类一起清。
- `pg_ctl -o "-k <相对路径>"` 必失败（启动后会 chdir 到 PGDATA），一律传绝对路径。
- 不要 `pkill -f 'data/pgdata'`：模式会匹配到自己的 shell。

### 依赖 / 打包

- torch 与 torchvision 必须同锁 `pytorch-cpu` 源，否则 torchvision 装成 CUDA wheel。
- 缓存与 HOME 要收进 `data/`（`MAMBA_ROOT_PREFIX` / `CONDA_PKGS_DIRS` / `XDG_CACHE_HOME` / `HF_HOME`）。
- 只读 `~/.cache` 的环境给 uv 加 `UV_CACHE_DIR=$PWD/data/.uv-cache`。
- KDE Baloo 默认索引整个 `$HOME`，批量下载后可能吃满内存；本机已关闭内容索引
  （`balooctl6 config set contentIndexing no`），恢复时改 `yes`。
- OpenVINO 的遥测 warning 无害（会往 `$HOME/intel` 写 consent 文件），可忽略。

### 命名 / 导入

- 函数与模块同名会被包重导出遮蔽（`bootstrap()` vs `bootstrap.py`）→ 函数改名 `bootstrap_env`。

### WebUI / 前端

- HTML 转 markdown 别用 trafilatura（会抹平标题层级），用 BeautifulSoup 自写。
- Jinja 里 `job.items` 会解析成 dict 的 `.items` 方法 → 用 `job["items"]`。
- 「只刷新一次」的守门不能放 `sessionStorage`，终止条件放服务端。
- 鉴权不能前缀宽匹配（`/loginfoo` 可绕过 `/login`），用精确集合 + 前缀分离。
- marked.js 输出必须过 DOMPurify；SSE 一律 `tojson` + 文本节点。
- CPU 密集接口不要写成 `async def`（单 worker 会卡住整站）。

### 测试

- 别往全局迁移登记表塞测试用重名版本；写真实库的测试要在 `finally` 里清理。

### 外部服务

- DeepSeek 带 tools 必须回传 `reasoning_content`，否则 400。
- Bing 直连三件套缺一不可：Firefox UA + 先访问首页取 cookie + 查询 URL 带 `form=QBRE`；
  真实链接要解 `/ck/a` 的 `u=` base64。

## 12. 路线与待定

**主线**：v1.0 的主体是人格 / 角色载体；记忆系统暂停中，重启由开发者决定。之后是语音链路
（STT → LLM → TTS）、知识库第二阶段（PDF / 混合检索）、GraphRAG。阶段划分与验收见
`docs/forAiDoc/V1.0-PLAN.md`（阶段划分将被 `todolist.md` 的两阶段计划取代）；
待办与阶段计划见 `todolist.md`。

**已定方向（未实现）**：

- TTS 起步用 Edge TTS（免费），Azure TTS 备选；STT 待选型。
- 知识库第二阶段：PDF 与混合检索。

**明确不做（短期）**：

- 独立文档站（另起仓库，暂不做）。
- autorun 定时与主动任务（只留设计，暂不实现）。
- 对外接口 / 插件系统（先搁置，只做总线内部调用）。
- 场合与去向模型（含独白）：只写文档，不写代码。

**待定（不要替开发者做决定）**：

- STT 选型（候选：Groq Whisper / 通义听悟）。
- 流式回复期间用户提前输入的文本：丢弃、缓存后交给 Aris，还是装没听见；判断依据待定。
- mypy 从 `core` + `store` 扩到其余模块的时间。
