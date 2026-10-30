# 开发进度

> 只记**当前**状态与在手的事；历史条目在 `docs/archive/PROGRESS-2026-10.md`。
> 开工前先读本文件，再读 `todolist.md`（待办唯一真相源）与 AGENTS.md §10 路由。

## 当前版本

`0.4.4`（tag `v0.4.4`，正式版，2026-10-30 发布）。下一阶段：**标准化 + v1.0 开发准备**。

## 当前阶段

**v0.4.4 已完成并发布**（施工文档已归档至 `docs/archive/v0.4.4.md`）。
当前进入 **v1.0 前的标准化**（提交规范 / 文档 / 项目结构；CI 与 i18n 留到 v1 期间）。

| 工作包 | 状态 |
|---|---|
| W1 统一数据目录（`paths.py`） | 完成 |
| W2 配置收口（`data/config/` + TOML 密钥 + 种子模板） | 完成 |
| W3 CLI 事实入口（`info` / `config` / `modules`） | 完成 |
| W4 serve 不被模块依赖（运行时归 `behavior/runtime.py`） | 完成 |
| W5 LLM 退休机制退役（`data/state/llm-list-missing.json`） | 完成 |
| W6 工程小件（AGPL / alpha / archive / CLAUDE.md） | 完成 |

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

## 已落地（v0.4.4）

- **W1**：`src/aris/paths.py` 是路径唯一来源（`ARIS_DATA_DIR` > 开发树 `./data` > `~/.project-aris`）；
  `aris info` 打印解析结果与来源。
- **W2**：配置统一在 `data/config/`（`settings.toml` / `secrets.toml`(0600) / `providers.toml` /
  各模块 toml），种子模板随包在 `src/aris/seed/config/` 并在 `serve.assemble()` 前幂等播种；
  `.env` 机制移除（配置一律 TOML，环境变量优先）。
- **W4**：运行期单例（`build_engine` / `get_runtime` / `peek_runtime` / `reset_runtime`）归
  `behavior/runtime.py`，删除 `serve/assembly.py`；`chat` / `cli` / serve 步骤改为依赖 behavior。
  装配失败经 `assembly_error()` 在启动清单与 `aris doctor` 如实报错；新增
  `tests/test_import_boundary.py`（AST 扫描，除 `serve/` 与 `cli.py` 外禁止 import serve）。
- **W5**：退休 / 宽限期 / 自动恢复机制删除；同步后消失的模型只写入
  `data/state/llm-list-missing.json`（`{provider, model, last_seen}`，幂等合并、跨提供方保留）；
  `aris llm missing list`（旧 `retired` 留一版别名）与 WebUI「缺失记录」tab 均只读。
- **W6**：许可证换 AGPL-3.0-or-later（`COPYING` + pyproject + README/AGENTS 口径）；
  版本脚本支持 `alpha-vX.Y.Z`（只在 develop、占号，含测试）；`docs/archive` 取消跟踪
  （本机保留、`.gitignore` 排除）；新增 `CLAUDE.md -> AGENTS.md` 软链。
- **W3**：新增 `src/aris/modules.py`（7 个模块开关 + 依赖级联 + modules.toml 读写）；
  `serve.assemble()` 先读开关再 import，关闭模块的启动步骤标 skipped、依赖方记 error 不退出；
  CLI 新增 `aris info` / `aris config path|list|show|validate|env` / `aris modules list|status|enable|disable`；
  `knowledge.toml` 的 `enabled` 并入 modules.toml。

## 阻塞 / 待决

- **安装态数据目录**：暂用 `~/.project-aris`；上不上 XDG（`~/.local/share/aris`）待定（不上 Flatpak）。
- **memory 设计重审**：暂不恢复开发；重启时间按开发者意愿决定。
- STT 选型：候选 Groq Whisper / 通义听悟。
- mypy 检查范围：当前只查 `core` + `store`，扩到其余模块的时间待定。

## 下一步

1. 阶段收官：`bump-version.sh 0.4.4` → `release-check.sh` → 合并 main → tag `v0.4.4`。
2. 可选技术债：`cli.py` 拆包（W3 建议项，未做）、模块开关测试的总线快照隔离（3.5 建议项）。

