# 开发进度

> 只记**当前**状态与在手的事；历史条目在 `docs/archive/PROGRESS-2026-10.md`。
> 开工前先读本文件，再读 `todolist.md`（待办唯一真相源）与 AGENTS.md §10 路由。

## 当前版本

`0.4.3`（tag `beta-v0.4.3`）。下一阶段的目标是**正式 v0.4.4（地基版）**。

## 当前阶段

**v0.4.4 规划完成，尚未开工。** 范围与决策见 `todolist.md` 末尾「备注（2026-10-28 定）」：

- **W1** 统一数据目录（新增 `paths.py`，清硬编码）
- **W2** 配置收口（`data/config/`；`.env` 转 TOML 迁入；拆 `settings.toml` + `secrets.toml`）
- **W3** CLI 事实入口（`info` / `config` 只读 / `modules` 开关）
- **W4** serve 不被模块依赖（运行时对象移到 `behavior/runtime.py`）
- **W5** LLM 退休机制退役（只留 `data/state/llm-list-missing.json`）
- **W6** 工程小件（AGPL、alpha 渠道、archive 取消跟踪、`DEV-FLOW.md`、`CLAUDE.md` 软链）

建议顺序：W1 → W2 → W3；W4 / W5 / W6 可并行。

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

## 已定但未实现

- 配置全部收进 `data/config/`；`.env` 改为 TOML，拆 `settings.toml` + `secrets.toml`（后者 0600）。
- 模块开关按模块粒度（store / knowledge / mcp / behavior / webui / character / voice）；工具开关留 v1.0。
- CLI 功能必须 ≥ WebUI；`serve` 不得被任何模块 import。
- alpha 渠道只在 `develop` 发布并占用数字线。
- 旧配置 / 旧数据迁移与兼容性：v1.0 之前不承诺。

## 阻塞 / 待决

- **memory 设计重审**：暂不恢复开发；重启时间按开发者意愿决定。
- STT 选型：候选 Groq Whisper / 通义听悟。
- mypy 检查范围：当前只查 `core` + `store`，扩到其余模块的时间待定。

## 下一步

1. 开 `feat/paths`，做 W1（统一数据目录 + 守卫测试 + `aris info`）。
2. W1 合并后接 W2（配置 TOML 收口）。
3. 每项收工用 `date` 记录实际工时，回填估算。
