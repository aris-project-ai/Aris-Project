# 开发进度

> 只记**当前**状态与在手的事；历史条目在 `docs/archive/PROGRESS-2026-10.md`。
> 开工前先读本文件，再读 `todolist.md`（待办唯一真相源）与 AGENTS.md §10 路由。

## 当前版本

`0.4.3`（tag `beta-v0.4.3`）。下一阶段的目标是**正式 v0.4.4（地基版）**。

## 当前阶段

**v0.4.4 进行中**（施工文档：`docs/process/v0.4.4.md`；范围见 `todolist.md` 末尾备注）。

| 工作包 | 状态 |
|---|---|
| W1 统一数据目录（`paths.py`） | 完成 |
| W2 配置收口（`data/config/` + TOML 密钥 + 种子模板） | 完成 |
| W3 CLI 事实入口（`info` / `config` / `modules`） | 待做 |
| W4 serve 不被模块依赖（运行时归 `behavior/runtime.py`） | 完成 |
| W5 LLM 退休机制退役（`data/state/llm-list-missing.json`） | 待做 |
| W6 工程小件（AGPL / alpha / archive / CLAUDE.md） | 待做 |

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

## 阻塞 / 待决

- **安装态数据目录**：暂用 `~/.project-aris`；上不上 XDG（`~/.local/share/aris`）待定（不上 Flatpak）。
- **memory 设计重审**：暂不恢复开发；重启时间按开发者意愿决定。
- STT 选型：候选 Groq Whisper / 通义听悟。
- mypy 检查范围：当前只查 `core` + `store`，扩到其余模块的时间待定。

## 下一步

1. W5（退休退役）→ W6（工程小件）→ W3（CLI + 模块开关，最大）。
2. 每项收工用 `date` 记录实际工时，回填 `docs/process/v0.4.4.md` §4。
