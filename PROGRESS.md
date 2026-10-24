# 开发进度

> 本文件只记**当前**状态与在手的事；历史条目（含各轮开发记录与踩坑）在
> `docs/archive/PROGRESS-2026-10.md`。
> 开发前先读本文件，再按 `AGENTS.md` §10 的文档路由取模块文档。

## 当前版本

`0.4.2.1`（`__version__ = "0.4.2.1"`，tag `beta-v0.4.2.1`）。下一个目标是 **v1.0.0**。

## 模块状态

| 模块 | 状态 |
|---|---|
| `core/` | 完成：CMCB 总线（服务注册 + 事件 + 审计）、LLM 多提供方 / fallback / 流式 / 工具调用 |
| `store/` | 完成：便携 PG + pgvector、本地 embedding（Bekko 384 维）、迁移机制、向量 helper；可迁移性与启动幂等已落地 |
| `knowledge/` | 首期完成：摄入 / 分块 / 纯向量检索 / CLI / agent 工具 / WebUI 知识库页 |
| `behavior/` | 完成：agent loop、工具注册表、内置工具、skills 系统 |
| `chat/` | 完成：会话逻辑 + TUI（`aris chat`，调试用） |
| `character/` | 完成：角色载体 `data/characters/<cid>/`；`character.system_prompt(cid)` / `list` / `resolve` |
| `serve/` | 完成：`aris serve` 一条命令起全套；唯一组装根装配一份进程级运行时 |
| `webui/` | 完成：鉴权 / 仪表盘 / 审计 / 提供商 / 技能 / 配置 / 日志 / 知识库；配置页体验待重做 |
| `memory/` | **暂停开发**：设计审查发现重大缺陷，重启时间由开发者决定（见 `docs/forAiDoc/MEMORY.md`） |
| `voice/` | 占位：STT / TTS 选型未定 |
| `autorun/` | 方向已定，暂不实现（只留设计） |

## 当前聚焦

- **工程化 P0（已完成，随 `chore/tooling` 合并进入 develop）**：ruff + mypy + `scripts/check.sh`；
  wheel 补齐 WebUI 模板 / 静态文件、`py.typed` 与 GPL-3.0-or-later 元数据；全量测试 163 passed。
- **文档整治**：目录已统一为 `docs/forAiDoc/`；其余文档按 AGENTS.md 标准分批清理
  （删历史与日期、过程迁 `docs/archive/`、重复内容只留一处）。
- **v1.0**：`character` 已完成；`memory` 暂停，原 M3（会话落库）之后的阶段一并挂起。
  character 之后的推进方向等 memory 重审结论，或由开发者另行指定。

## 阻塞 / 待决

- **memory 设计重审**：暂不恢复开发；重启时间按开发者（尤其是莫琳）意愿决定。
- `config/` 是否整体迁到 `data/config/`：模板 / 示例配置放哪未定。
- STT 选型：候选 Groq Whisper / 通义听悟。
- mypy 检查范围：当前只查 `core` + `store`，扩到其余模块的时间待定。

## 下一步

1. **重置其余文档**：`docs/forAiDoc/*` 还没按 AGENTS.md 的标准清理——删除历史与日期、
   把过程迁入 `docs/archive/`、重复内容只留一处；逐份来，改完顺手更新本文件。
2. 等 memory 设计重审结论，再决定后续主线。
3. 其他可插入项见 `docs/forAiDoc/BACKLOG.md`。
