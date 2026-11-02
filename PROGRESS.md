# 开发进度

> 只记**当前**状态与在手的事；历史条目不在仓库内。
> 开工前先读本文件，再读 `todolist.md`（待办唯一真相源）与 AGENTS.md §10 路由。

## 当前版本

`0.4.5`（tag `v0.4.5`，正式版，2026-11-01 发布）。当前做 `0.4.5.1` 收尾补丁：
**文档修理 + 已有 CI 修复，不加任何功能**。

## 当前阶段

**v0.4.5 已发布**：变更记录、CI 分档、发版脚本与文档合规落地。
`check` 本地通过（`bash scripts/check.sh`）；推送 `develop` 后确认远端绿。`integration` 还没在
远端跑绿——等 0.4.5.1 发版 PR 首次真实运行（本版修掉了它选中系统 PostgreSQL 的问题）。

**v0.4.5.1 进行中**，完成后进入 **v1.0「跨越」**：

| 项 | 状态 |
|---|---|
| pytest 假失败（模块级 `skipif` 早于 autouse fixture） | 已修，随 0.4.5.1 发布 |
| integration 选中系统 PG、缺 pgvector | 已修（`ARIS_PG_SOURCE=project`），待发版 PR 验证 |
| `docs/dev-flow.md` 错误陈述、`gh` 改网页优先 | 本版修 |
| `PROGRESS.md` 刷新、`V1.0-PLAN.md` 归档、`todolist.md` 结算 | 本版做 |
| `CHANGELOG` 归档 `[0.4.5]` 并封 `[0.4.5.1]` | 发版时做 |

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
| `memory/` | **暂停开发**：设计审查发现重大缺陷，重启由开发者决定（见 `docs/forAiDoc/MEMORY.md`） |
| `voice/` | 占位：STT / TTS 选型未定 |
| `autorun/` | 方向已定，暂不实现（只留设计） |

## v0.4.5 已落地

- **变更记录**：根 `CHANGELOG.md` 只留 `[Unreleased]` 与最新版本，旧版本归档到 `changelogs/`。
- **CI 分档**：`check`（所有 PR / `develop` / `main` 推送）、`integration`（发版 PR 到 main，
  真 PG + embedding + 全量测试 + 冷启动）、`smoke`（alpha tag）。
- **发版脚本**：`scripts/release.sh` 只做本地准备（校验、切分支、bump、检查），不推送、不打 tag。
- **文档与合规**：`docs/dev-flow.md` 发版节重写、README 变更记录与许可证段、`NOTICE`。

## 0.4.5.1 修复

- `tests/test_store_portability.py`：PG 二进制探针的跳过条件改为运行时判断。模块级 `skipif`
  在收集阶段求值，早于 autouse fixture 把 `shutil.which` 打成 `None`；装了系统 PostgreSQL 的
  CI runner 会先被判成「已安装」，用例内再探测却得到「未安装」，变成假失败。
- `ARIS_PG_SOURCE=auto|project|system`：收窄便携 PG 探针链。系统 PostgreSQL 未必装
  pgvector，`integration` 设 `project` 强制走 `data/pg`（`ARIS_PG_BIN` 仍最高优先）。
- `docs/dev-flow.md`：修正「fork PR 首次带 workflow 也能跑」的错误陈述，补 bootstrap 坑；
  `gh` 命令改为网页操作步骤。

## 阻塞 / 待决

- **上游仓库设置**：需开发者确认已开启 **Allow auto-merge** 并导入 `.github/rulesets/`
  （`main` 要求 `check` + `integration`，`develop` 要求 `check`）。0.4.5 因 `main` 上还没有
  workflow 走了 bypass 合并（bootstrap），0.4.5.1 起按正常 auto-merge 验证。
- **安装态数据目录**：暂用 `~/.project-aris`；上不上 XDG（`~/.local/share/aris`）待定（不上 Flatpak）。
- **memory 设计重审**：暂不恢复开发；重启时间按开发者意愿决定。
- STT 选型：候选 Groq Whisper / 通义听悟。
- mypy 检查范围：当前只查 `core` + `store`，扩到其余模块的时间待定。
- `CONTRIBUTING.md` / `SECURITY.md`：0 字节占位，v1 P7 重写（面向人类、不引用 AI 文档）。

## 下一步

1. **0.4.5.1 发版**：`bash scripts/release.sh 0.4.5.1` → 归档 `[0.4.5]`、封 `[0.4.5.1]` →
   `release-check.sh` → 上游 PR（**不 bypass**，等 `check` + `integration` 全绿）→ 开 auto-merge →
   tag `v0.4.5.1` → `main → develop` 回合并。
2. **v1.0「跨越」**：施工入口 `docs/process/v1.0.0-prep.md`，待办见 `todolist.md`。
3. 可选技术债：`cli.py` 拆包、模块开关测试的总线快照隔离。
