# 开发进度

> 只记**当前**状态与在手的事；历史条目不在仓库内。
> 开工前先读本文件，再读 `todolist.md`（待办唯一真相源）与 AGENTS.md §10 路由。

## 当前版本

`0.4.6`（tag `alpha-v0.4.6`，alpha 开发通道，2026-11-03）。上一个正式版是 `0.4.5.1`。
**v1.0「跨越」开发周期从 `alpha-v0.4.6` 起算**。

## 当前阶段

**v1.0「跨越」开发周期已启动**（`alpha-v0.4.6`），已进入施工：S1 从外部组件清单开始落代码，其余批次先收敛文档与决策。

- **记忆系统对外定名 APEMS**（Aris Project Engram Memory System）：`Engram` 是名、`Memory System`
  是性质；代码仍叫 `memory`，界面导航仍叫「记忆」（2026-11-06 复核）。
- **插件系统整体推迟 v1.1**，v1.0 不做也不预留接口；草案移到 `docs/process/v1.1-plugin-system.md`。
- **决策模型去掉 `main_llm`**：只保留 `off | dedicated`，失败降级到概率 / 规则；消息密集时先攒批再判。
- **记忆**：重要性由抽取时模型标注（`importance ≥ 0.8` → 「重要」预设，weight 2048、直接常驻）；
  真实命中只续命（重置 `last_reinforced_at`、累加 `hit_count`，不改 weight）；中期在 30 天内
  ≥5 个不同自然日命中的晋升长期（止步于长期）；兜底检索 / 随机回忆不写库。
  大会话（时间聚类）保留用于作息 / 活跃度查看，但 v1 不做大会话总结（小会话总结即 compact）；
  换 embedding 模型走影子表全量重建。
- **外部 PostgreSQL**：保留支持；备份改用 `pg_dump` 逻辑导出，版本不匹配时明确标注「数据库未备份」。
- **S1 T6 已落地（2026-11-07）**：`infra/components.py` 收编 PG / pgvector / micromamba / embedding
  的版本与校验值（`Archive` / `CondaPackage` / `Model` 三种条目）；`store/bootstrap.py` 删掉版本常量、
  修掉 arch 写死；本地 embedding 改为锁 HF commit（原来读 `refs/main`，是浮动的）；
  `aris components list [--json]` 只读、`doctor` 增主版本对账。镜像写 `store.toml` 的 `[mirror]`
  （只换 URL，sha256 仍取清单）；**uv 不进清单**（运行期不用，归 S13 打包脚本）。
  版本仍钉 `17` / `0.8.1`，目标 `18.6` / `0.8.6` 在 S5 连同 `data/pgdata` 重建一起切。
- **配置档**：`serve.toml` / `webui.toml` 不随档（避免恢复别人的备份后端口变化）；GUI 不得写死端口。
- **施工顺序已定**（2026-11-03）：v1 按 S1–S14 批次推进（元数据与 i18n 基建 → WebUI 外壳 →
  备份 → 配置档 → 存储适配 → 消息模型 → LLM → 设置页 → 消息平台 → 记忆/角色 → WebChat/决策/autorun
  → 知识库二期/skills → GUI/打包/CD → i18n 收口），见 `docs/process/v1.0.0-prep.md` §5。
- **GUI 定为 MyGO（Go）**：工具链只放 `gui/`（不需要 Bun），打包配方自己写；后端地址走
  `<data>/state/webui.json`（addr / pid / 版本），关窗只关 GUI 并提供「关闭后端」按钮。
- **WebChat**：保留 `Dashboard | Chat` 分段切换；切到 Chat 后侧栏换成角色列表，不做会话切换；
  输入区 = 文本 + 图片；思考链 / 工具调用 / 记忆命中是三个用户开关（默认全关）。
- **多角色**：平台实例与角色绑定（可绑多个，实例排他），路由 = 实例 → cid → 唯一会话；
  群聊 / 共用实例留 v1.x。
- **图片**：按模型 `图形理解` 能力投影——原生发图 / 可选「图片转述」/ 占位；发送前限边长、压体积、
  动图拼九宫格（AstrBot 同思路）。
- **关于页彩蛋**：白色图标触发；默认**外链跳转**到东方红一号卫星在轨播发电子音版本的公开页面
  （普通超链接、新标签、不内嵌、不直链、不打包）。除版权外还有四层合规：软件许可（AGPL 覆盖不到
  第三方资产 / 打包规则要求许可证）、平台内容政策、链接方式、跨境分发——详见 `v1.0.0-prep.md` §4.23。
  **硬规则：包内不得出现任何《东方红》音频文件**。
- **S1 施工文档已写**：`docs/process/v1/S1-foundation.md`。工具开关只做按工具（owner 级归插件系统 v1.1），
  `tools.toml` 只记 `[disabled] tools`，关闭 = 移出工具面 + 拒绝执行；模块关闭时配置项仍列出。
- **store 总线化已排进 S5**（2026-11-06 定）：业务模块不再直接 import store，统一走 `store.*`；
  连接对象走**方案 A（池化上下文）**——`store.connect` 从 `psycopg_pool` 借还、pgvector 适配器在池的
  `configure` 注册、事务边界仍归调用方，见 `v1.0.0-prep.md` §3.7。
- **外部组件清单定案**（2026-11-06）：`src/aris/infra/components.py`（**Python 常量**，不用 TOML），
  v1 只收 PG + embedding，排 **S1**；用户层 `data/config/components.toml` 只能覆盖 `url`（镜像），
  `sha256` 永远在代码里（§3.8，§7-28 已结）。
- **v1prep 工程化（2026-11-06）**：§4.5 补全搜索引擎注册表契约（落点拆 `search_engines.toml` 只是建议，
  待拍板）；§4.8 角色系统按代码校正——`character.toml` + `worldview/relations/growth.md`
  （`prompt.md` 不存在）、cid 规则与 12 位十六进制自动生成冲突、`CharacterStore.create()` 无 cid 校验
  （S10 开入口前必须补，否则是目录穿越）；§4.14 skills 导入定下「内置 / 用户两层根 + 原子落盘 + 无沙箱」。
- **记忆模型校正（2026-11-06）**：「重要」恢复为模型在抽取时打标（`weight = 1024`、直接常驻，
  不进则已、进则顶格）；检索退化为续命（只重置 `last_reinforced_at`，不改 `weight`）；
  晋升改为 5 个自然日（可配 5~7）且止步于长期；`hit×128` / `384` / `recall_bonus` 全删。
  详见 `MEMORY.md` §1 / §4。
- **`is_user` → `is_owner`（2026-11-07 定）**：原字段把「当前发言人」「归属」「是不是人」三件事挤成一个 bool，
  与「群聊 / 多平台对话对象不止一个」自相矛盾。改为 **`is_owner`（这个角色属于谁）**：至多一个、可以没有、
  只由用户手动设，数据库用部分唯一索引保证；当前发言人改由消息信封 `speaker` 经 `memory_identities` 解析。
  抽取 schema 不再输出该字段；WebUI 人物页与 CLI `aris memory owner` 对等。显示文案可配
  `owner_label`（默认「主人」，可改「管理员」等）。详见 `MEMORY.md` §5.1 / §10 / §15。
- **换 embedding 模型后的旧表保留期（2026-11-07 定）**：`retention_days` 默认 7 天、可配 0~30
  （0 = 切换成功即删）；保留期内可回滚，到期自动清理。
- **记忆库元信息 = 库自描述（2026-11-07 定，方案 A）**：每个库内部一张单行 `memory_library`
  （full 在该库 PG schema 内，lite 在该库 SQLite 文件内），**不设全局注册表**；不存 `initialized`
  （启动探测）、不存 `cid` 绑定、不存大小 / 条数；不做 `description` / `last_used_at`。
  物理位置由 `library_id` 推导（schema `mem_<id 前 12 位>`、文件 `data/memory/libraries/<id>.sqlite`），
  `character.toml` 只存 `library_id`。结构迁移逐库记在库内 `memory_migrations`——全局
  `store_schema_migrations` 的 `(owner, version)` 表达不了每库进度不同。详见 `MEMORY.md` §1.1 / §10。
- **`importance` 保留（2026-11-07 评估）**：只作抽取原始分，用于定预设、审计、改阈值后重新分层；
  运行期注入与排序只看 `w_eff`，不再参与重排。
- **会话冷却同步为 1 天（2026-11-07）**：`AGENTS.md` 与 `PORTABILITY-AND-SINGLE-SESSION.md` 一并改成
  「默认 1 天，可配、最大 5 天」，与 `MEMORY.md` §9.0 一致。
- **记忆文档一致性修订（2026-11-07）**：补 `memory_hits`（晋升要 `DISTINCT` 自然日，原 DDL 无处记录）、
  `memory_identities`（speaker → 实体）、`memory_messages` 的 `speaker` 等字段；`valid_to` 与
  `superseded_at` 拆成世界时间 / 系统时间；`stale` 落列；事件参与者只存 `memory_event_entities`；
  检索重排改为 `0.7 rel + 0.3 norm(w_eff)`（原 `importance` + `recency` 与 `w_eff` 重复计权）；
  两周记检索改用真实窗口边界；钉住上限与关键块配额对齐；工具面明确为 2 读 2 写。
- **衰减改连续曲线（2026-11-07）**：`w_eff = weight × 0.5^(Δt/H)` 取代整数位移 `>>`；
  `weight` 明确为**基准值**、永不随衰减变小；仍惰性计算、无定时任务。为保住原来的
  「重要」146 天常驻，基准从 1024 提到 **2048**（H 仍 73，彻底不可达仍是 584 天）；
  中期 `<8` 从约 70 天缩到 **约 56 天**。排序要可索引时再把算好的分物化成派生 `score`
  缓存（零迁移），v1 不做。
- **印象层（2026-11-06 定）**：`facts` 表取代 `relations`（claim 而非 truth：`confidence` / `source_kind` /
  `evidence` / 有效期 / `status`，`inferred` 默认不进常驻）；人物卡 `[记忆·人物]` 取代关系摘要卡，
  按人分卡（槽位段来自事实库、自由段由角色自写 ≤150 字）；事件加可选 `mood`（七档预设 + 允许自拟）。
  详见 `MEMORY.md` §5 / §6.1。
- **memory-lite 与 full 同构（2026-11-06 定）**：事实层三表（`memory_entities` / `memory_facts` / `memory_event_entities`）都实现，
  只砍递归 CTE；消歧靠 `aliases` 精确匹配 + 人工合并；人物卡做成通用开关 `inject.people_card`
  （默认开、两个后端共用），有效槽位 <2 自动不渲染。
- **设置页分类定案（2026-11-06）**：合并为 **8 个 tab**（聊天 / 模型与搜索 / 记忆 / 知识库 / 存储与向量 /
  服务与网络 / 日志与通知 / 界面），文件→tab 映射在 `infra/config_items.py` 一处定义、顺序显式；
  `settings.toml` 允许字段级 `category` 覆盖；section 目标 3~12 项，`collapsed` 只按冷门程度用；
  `serve.skip` / `llm_providers_file` 标 `hidden`；搜索补「跨 tab 跳转 + 高亮」，见 §3.3。
- **PG / pgvector 定版本（2026-11-06）**：改钉 **`postgresql=18.6` + `pgvector=0.8.6`**（PG 17 最高只能配
  pgvector 0.8.1，两者由 `libpq` 绑死）；版本常量进 `infra/components.py`，改它即升级、随版本发布；
  `MAMBA_URL` 的 arch 写死一并修掉（aarch64 目前装不了）；micromamba 也收进该清单以支持镜像覆盖。
  **本机需一次性重建 `data/pgdata`**（17→18），并丢弃 `data/knowledge/` 的两篇测试文档（S5 动手时做）。
  另：`architecture-findings-2026-11-06.md` 里 6 条未决项已并入 `v1.0.0-prep.md` §7-32~37。
- **打包与 CD 定案（2026-11-06）**：**M1（运行时 uv）确认**——包只装源码 + `uv.lock` + 启动器，
  解释器由 uv 在首启安装；**Arch 声明 `depends=('uv')`、deb 内置钉死的 uv**（Debian 无 uv 二进制包，
  sid 只产 `python3-uv-build`）；命名定为 **包名 / app-id / 目录 `ariscore`**，命令仍 `arisp` / `arisp-gui`
  （`aris` 被 GNU Aris 占用）。首启下载 ≈ CPython 73 MB + 基础依赖（装好 129 MB）+ PG 约 40 MB，
  本地 embedding 按需再补 1.5 GB。详见 §4.15。
- **Python 钉 3.14（2026-11-06）**：仓库根加 `.python-version` = `3.14`。原 `requires-python >=3.14`
  会让 uv 选到 3.15，而 `pydantic-core` / `jiter` 无 cp315 轮子 → 转源码编译。
  **暂不升 3.15**：`openvino` / `openvino-tokenizers` 任何版本都没有 cp315 wheel（C++ 扩展），
  其余依赖已就绪；等 OpenVINO 出新版再整体升。
- **旧文档集中清理不绑阶段**（2026-11-04 定），见 `v1.0.0-prep.md` §10.1。
- **S13 施工文档已写（2026-11-06）**：`docs/process/v1/S13-packaging.md`——产物与命名、安装布局、
  首启启动器（环境变量 + stamp 重同步 + 失败处理）、PKGBUILD / deb 要点（含 trixie 的
  `libgtk-3-0t64` / `libwebkit2gtk-4.1-0`）、`.desktop`、CI 矩阵、验收清单。
- **命名一致性校对（2026-11-06）**：**CMCB 服务表整表删除**（清单以 `aris services list` 为准，
  文档不再维护，必然漂移），命名规则改成「功能域 + 2~3 段」，`AGENTS.md` §6 / §7 同步；
  种子模板删掉指向已消失的 `docs/developDoc/` 的注释，`store.toml` 的 `--extra embedding`
  改为 `--group embedding`；`paths.py` / `todolist.md` 里残留的旧命令名 `paris` 改为 `arisp`；
  安装态数据目录改名 `~/.project-aris` → **`~/.aris-project`**（源码树仍用仓库 `data/`）；
  显示名统一为 **`Aris Project`**；删掉过程文档 `TUI-问题修复.md`。
  命令维持双名：`arisp` 只出现在「以包形式安装」的语境；记忆表统一 `memory_*` 前缀
   （`memory_entities` / `memory_facts` / `memory_event_entities`）。命名议题全部结案。
- v1 文档仍有未定项（STT 选型、流式提前输入、记忆检索调参等），见同文 §7。

| 项 | 状态 |
|---|---|
| pytest 假失败（模块级 `skipif` 早于 autouse fixture） | 已发布 |
| integration 选中系统 PG、缺 pgvector | 已发布，远端 integration 已绿 |
| `db init` 后紧跟 `db start` 误判端口 | 已发布（`4b9bd80`） |
| `docs/dev-flow.md` 错误陈述、`gh` 改网页优先 | 已发布 |
| `PROGRESS.md` 刷新、`V1.0-PLAN.md` 归档、`todolist.md` 结算 | 已完成 |
| `CHANGELOG` 归档 `[0.4.5]` 并封 `[0.4.5.1]` | 已完成 |

发版过程记录：tag `v0.4.5.1` 打在 `main` 的合并提交 `ea73a74` 上；发布期间上游尚未开启
**Allow auto-merge**，0.4.5.1 的两步 PR 均为检查全绿后手动合并。

## 模块状态

| 模块 | 状态 |
|---|---|
| `core/` | 完成：CMCB 总线（服务 + 事件 + 审计）、LLM 多提供方 / fallback / 流式 / 工具调用 |
| `store/` | 完成：便携 PG + pgvector、本地 embedding（Bekko 384 维）、迁移机制、向量 helper |
| `knowledge/` | 首期完成：摄入 / 分块 / 纯向量检索 / CLI / agent 工具 / WebUI 页 |
| `behavior/` | 完成：agent loop、工具注册表（世代同步）、内置工具、skills；工具声明式收编（`.ai_tools`） |
| `mcp/` | 完成：通用 MCP 客户端（stdio / streamable-http，owner 线程 + 同步总线服务） |
| `chat/` | 完成：会话逻辑 + TUI（调试用） |
| `character/` | 完成：角色载体 `data/characters/<cid>/` |
| `serve/` | 完成：`aris serve` 一条命令起全套；唯一组装根 |
| `webui/` | 完成：鉴权 / 仪表盘 / 审计 / 提供商 / 技能 / 配置 / 日志 / 知识库；配置页体验待重做 |
| `memory/` | v1 P4 开工（对外名 **APEMS**）；契约已按 2026-11-03 决策更新（见 `docs/forAiDoc/MEMORY.md`） |
| `voice/` | 占位：STT / TTS 选型未定 |
| `autorun/` | 方向已定，暂不实现（只留设计） |

## v0.4.5 已落地

- **变更记录**：根 `CHANGELOG.md` 只留 `[Unreleased]` 与最新版本，旧版本归档到 `changelogs/`。
- **CI 分档**：`check`（所有 PR / `develop` / `main` 推送）、`integration`（发版 PR 到 main，
  真 PG + embedding + 全量测试 + 冷启动）、`smoke`（alpha tag）。
- **发版脚本**：`scripts/release.sh` 只做本地准备（校验、切分支、bump、检查），不推送、不打 tag。
- **文档与合规**：`docs/dev-flow.md` 发版节重写、README 变更记录与许可证段、`NOTICE`。

## 0.4.5.1 已落地

- `tests/test_store_portability.py`：PG 二进制探针的跳过条件改为运行时判断。模块级 `skipif`
  在收集阶段求值，早于 autouse fixture 把 `shutil.which` 打成 `None`；装了系统 PostgreSQL 的
  CI runner 会先被判成「已安装」，用例内再探测却得到「未安装」，变成假失败。
- `ARIS_PG_SOURCE=auto|project|system`：收窄便携 PG 探针链。系统 PostgreSQL 未必装
  pgvector，`integration` 设 `project` 强制走 `data/pg`（`ARIS_PG_BIN` 仍最高优先）。
- `choose_port` 复用「本实例已在跑」的端口，`start` / `stop` 不再误清运行中实例的
  pid/socket：修 `db init` 后紧跟 `db start` 的幂等性回归。
- `docs/dev-flow.md`：修正「fork PR 首次带 workflow 也能跑」的错误陈述，补 bootstrap 坑；
  `gh` 命令改为网页操作步骤。

## 阻塞 / 待决

- **上游仓库设置**：`.github/rulesets/` 的必需检查已生效（0.4.5.1 两次 PR 都跑了
  `check` + `integration`）；**Allow auto-merge 已开启**（2026-11-03），后续发版 PR 可直接
  开 auto-merge。
- **`gh` CLI**：本机尚未安装；网页操作可用，配置后可简化 PR 与合并操作（auto-merge 的
  仓库开关仍需先在上游设置里打开）。
- **安装态数据目录**：**包安装用 `~/.aris-project`，源码树用项目根 `data/`**（2026-11-06 定）；不做 XDG、不上 Flatpak。
- **v1 文档仍在商议中**：`docs/process/v1.0.0-prep.md` §7 的待定项不要当成已定结论。
- STT 选型：候选 Groq Whisper / 通义听悟。
- mypy 检查范围：当前只查 `core` + `store`，扩到其余模块的时间待定。
- `CONTRIBUTING.md` / `SECURITY.md`：0 字节占位，S14 重写（面向人类、不引用 AI 文档）。

## 下一步

1. **S1 契约与地基**：配置项元数据 schema + `config.items`、i18n 基建 `t()`、工具开关、
   品牌 URL / egg-info 尾巴、旧文档清理（§10.1）；顺手带走 `cli.py` 拆包与 tests 分组。
2. **S1 已谈定，可开工**（2026-11-07）：元数据字段 / 英文 slug / 新增 `config` 命名空间 /
   `condition` 先落字段 / `config.items` 在 S1 提供 / 不做 `aris config items` /
   可关模块改显式 `register()`；细节见 `docs/process/v1/S1-foundation.md`。
3. **v1 文档剩余待定项**：GUI 框架、WebChat 界面、彩蛋等（§5.4 / §7）。
