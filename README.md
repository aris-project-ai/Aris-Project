# Project-Aris

> ## 隆重发布 beta v0.4.2
>
> uv sync && cp .env.example .env && uv run aris serve : 一键启动
> 本地优先: 自动下载便携版PostgreSQL + pgvector + Embedding 模型并加载
> WebUI: 实现简陋的WebUI管理界面

## 简介
在 2026-07 我看了Neuro-sama后，萌生了自建的想法，恰逢 Agentic 爆发，于是，在 AI （Opencode伟大，无需多言）的辅助下，本项目诞生了

## 快速开始

环境要求: Python >= 3.12,uv

### 启动
``` bash
uv sync && cp .env.example .env && uv run aris serve
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
- 运行时数据与日志均位于data/
- 数据库本体与数据也位于data/
- 密钥位于.env
- 配置文件位于config/

# 备份与迁移

通常情况下，只需在其他位置 git clone 本项目后将旧的 data/ 复制到新位置即可，如需迁移密钥与配置，请将 .env 与 config/ 也一并迁移

> 本项目的代码均由 AI 生成
