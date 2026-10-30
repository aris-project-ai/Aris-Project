# Aris-Project

> ## 隆重发布 beta v0.4.3
>
> uv sync && uv run aris serve : 一键启动
> 工具系统重构: 声明式工具收编 + 通用 MCP 客户端，任意 MCP server 即插即用
> 联网搜索兜底: 引擎池 Bing / Tavily(免 key 可用) / Exa，限流自动冷却换引擎

## 简介
在 2026-07 我看了Neuro-sama后，萌生了自建的想法，恰逢 Agentic 爆发，于是，在 AI （Opencode伟大，无需多言）的辅助下，本项目诞生了

## 快速开始

环境要求: Python >= 3.12,uv

### 启动
``` bash
uv sync && uv run aris serve
```

`aris serve` 会自动下载便携版PostgreSQL与embedding模型并启动，首次启动会较慢。
`aris serve`  允许部分启动，例如:

``` bash
aris serve --dry-run                 # 只进行体检并打印启动清单
aris serve --only store.db           # 只拉起数据库
aris serve --skip webui,store.embed
```

以及其他功能

``` bash
aris doctor  # 自检
aris chat    # 并不实用的TUI对话，不会自动拉起数据库和嵌入模型
```

## 其他命令
``` bash
aris llm list # 列出提供方和模型
aris llm check # LLM配置自检
aris llm test # 测试 LLM 连接
aris chat [消息] # 单次对话
aris db init\|start\|stop\|stop\|status\|psql # 手动操作数据库
aris knowledge add\|list\|remove\|search\|reindex # 手动操作知识库
aris web # 仅启动 WebUI
```
其他用法见 `aris -h` 与 `aris {doctor,llm,web...} -h`

# 数据相关

一切运行时数据都在 `data/`（不进 git，首次启动自动创建）：

- `data/config/` —— 配置与密钥（`secrets.toml` 权限 0600）；缺失时自动从随包模板播种
- `data/pgdata/` `data/pg/` —— 便携 PostgreSQL 与其数据
- `data/models/` —— 本地 embedding 模型
- `data/logs/` `data/state/` —— 日志与运行时状态

# 备份与迁移

只需把 `data/` 整个拷到新位置（配置、密钥、数据库、模型都在里面）；新机 `git clone` 后覆盖 `data/` 再 `uv run aris serve` 即可。

> 本项目的代码均由 AI 生成

## 许可证

本项目以 **AGPL-3.0-or-later** 发布，全文见 [`COPYING`](COPYING)。

## 参考项目

- [AstrBot](https://github.com/AstrBotDevs/AstrBot)
- [deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
- [opencode](https://github.com/anomalyco/opencode)
