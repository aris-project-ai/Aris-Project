# Aris-Project

[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-76bad9)](COPYING)
[![Python](https://img.shields.io/badge/python-3.14%2B-blue)](https://www.python.org/downloads/)

> ## 正式发布 v0.4.5（首个标准化版本）
>
> uv sync && uv run aris serve : 一键启动
> 本版定下变更记录、CI 与发版流程；第三方许可清单见 `NOTICE`
> v1.0 前接口与数据格式可能变动，介意的话先别接自己的数据。

<!-- 截图位：WebUI 仪表盘 / TUI 对话截图，补图后放在这里 -->

## 简介
在 2026-07 看了 Neuro-sama 后，萌生了自建的想法；恰逢 Agentic 爆发，于是，在 AI（Opencode 伟大，无需多言）的辅助下，本项目诞生了。
只不过不巧的是 DeepSeek Harness 与 dsh 插件的爆发，本项目显得有些迟滞。

## 快速开始

环境要求：Python >= 3.14、uv（Python 由 uv 自动准备，不需要手动安装）

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
aris info                     # 版本 / 路径 / 模块开关等环境事实
aris config path|list|show|validate|env   # 配置事实（只读，密钥脱敏）
aris modules list|status|enable|disable    # 模块开关（下一次启动生效）
aris llm list|check|test|fetch|missing    # 提供方与模型 / 缺失记录
aris chat [消息]              # 单次对话
aris db init|start|stop|status|psql      # 手动操作数据库
aris knowledge add|list|remove|search|reindex  # 手动操作知识库
aris web                      # 仅启动 WebUI
```
其他用法见 `aris -h` 与 `aris {doctor,llm,web...} -h`。

## 数据与备份

一切运行时数据都在 `data/`（不进 git，首次启动自动创建）：

- `data/config/` —— 配置与密钥（`secrets.toml` 权限 0600）；缺失时自动从随包模板播种
- `data/pgdata/` `data/pg/` —— 便携 PostgreSQL 与其数据
- `data/models/` —— 本地 embedding 模型
- `data/logs/` `data/state/` —— 日志与运行时状态

备份只需把 `data/` 整个拷到新位置（配置、密钥、数据库、模型都在里面）；新机 `git clone` 后覆盖 `data/` 再 `uv run aris serve` 即可。

## 文档与参与

- 变更记录：[`CHANGELOG.md`](CHANGELOG.md)（最新版本与未发布改动；历史版本在 [`changelogs/`](changelogs/)）
- 开发流程与提交规范：[`docs/dev-flow.md`](docs/dev-flow.md)
- 有问题或想改什么，先开 Issue 说清楚再动手，免得白做；项目是单人主导开发，回复可能慢，但都会看。

## 许可证

本项目以 **AGPL-3.0-or-later** 发布，全文见 [`COPYING`](COPYING)。

Copyright (C) 2026 kasamorin

第三方依赖（含前端静态资源）与设计参考项目的许可信息见 [`NOTICE`](NOTICE)。

## 参考项目

设计思路上重点参考过（不涉及代码复用，各自的许可与参考内容见 [`NOTICE`](NOTICE)）：

- [AstrBot](https://github.com/AstrBotDevs/AstrBot)
- [AIRI](https://github.com/moeru-ai/airi)
- [deepseek-harness](https://github.com/deepseek-ai/deepseek-harness)
- [opencode](https://github.com/anomalyco/opencode)
