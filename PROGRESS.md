# 开发进度

> 只记**当前**状态与在手的事；历史条目不在仓库内。
> 开工前先读本文件，再读 `todolist.md`（待办唯一真相源）与 AGENTS.md §10 路由。

## 当前版本

`0.4.6`（tag `alpha-v0.4.6`，alpha 开发通道，2026-11-03）。上一个正式版是 `0.4.5.1`。
**v1.0「跨越」开发周期从 `alpha-v0.4.6` 起算**。

## 当前阶段

**v1.0「跨越」开发周期已启动**（`alpha-v0.4.6`）。本轮只收敛 v1 文档与决策，不含功能代码：

- **记忆系统对外定名 APEMS**（Aris Project Engram Memory System）；代码仍叫 `memory`。
- **插件系统整体推迟 v1.1**，v1.0 不做也不预留接口；草案移到 `docs/process/v1.1-plugin-system.md`。
- **决策模型去掉 `main_llm`**：只保留 `off | dedicated`，失败降级到概率 / 规则；消息密集时先攒批再判。
- **记忆**：允许按「不同自然日真实命中 ≥3」把中期晋升长期；命中与随机回忆共用 384 加成额度；
  大会话（时间聚类）保留用于作息 / 活跃度查看，但 v1 不做大会话总结（小会话总结即 compact）；
  换 embedding 模型走影子表全量重建。
- **外部 PostgreSQL**：保留支持；备份改用 `pg_dump` 逻辑导出，版本不匹配时明确标注「数据库未备份」。
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
- **关于页彩蛋**：白色图标触发；默认《东方红》，特殊日期映射别的内容；音源授权未确认前不打包录音。
- v1 文档仍有未定项（Arch 安装位置、STT 选型、memory-lite 图形态等），见同文 §7。

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
- **安装态数据目录**：暂用 `~/.project-aris`；上不上 XDG（`~/.local/share/aris`）待定（不上 Flatpak）。
- **v1 文档仍在商议中**：`docs/process/v1.0.0-prep.md` §7 的待定项不要当成已定结论。
- STT 选型：候选 Groq Whisper / 通义听悟。
- mypy 检查范围：当前只查 `core` + `store`，扩到其余模块的时间待定。
- `CONTRIBUTING.md` / `SECURITY.md`：0 字节占位，S14 重写（面向人类、不引用 AI 文档）。

## 下一步

1. **S1 契约与地基**：配置项元数据 schema + `aris config items`、i18n 基建 `t()`、工具开关、
   品牌 URL / egg-info 尾巴、旧文档清理（§10.1）；顺手带走 `cli.py` 拆包与 tests 分组。
2. **S1 之前先谈定**：`aris config items` 的输出形态与元数据字段（这是全项目最底层契约）。
3. **v1 文档剩余待定项**：GUI 框架、WebChat 界面、彩蛋等（§5.4 / §7）。
