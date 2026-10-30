# 贡献指南（CONTRIBUTING）

> 面向人类贡献者。AI 协作开发规则见 [AGENTS.md](AGENTS.md)；本文件与 AGENTS.md 冲突时以
> AGENTS.md 为准。项目目前以个人开发 + AI 协作为主，外部贡献按同一套流程处理。

## 目录

- [工作流：Fork + PR](#工作流fork--pr)
- [分支命名](#分支命名)
- [提交信息](#提交信息)
- [本地验证](#本地验证)
- [文档要求](#文档要求)
- [发布与变更记录](#发布与变更记录)

## 工作流：Fork + PR

- 上游仓库：**aris-project-ai/Aris-Project**；日常开发在 fork
  **kasamorin/Aris-Project** 上进行。
- `main` 只进发布；日常开发全部汇到 `develop`。
- 外部贡献流程：
  1. fork 上游仓库，从最新 `develop` 拉 feature 分支；
  2. 在分支内小步提交（代码与文档分开）；
  3. 向 **`develop`** 提 Pull Request（不直接向 `main`）。
- PR 标题与提交 head 同格式（`type(scope): 描述`）；PR 描述写清：
  **改了什么 / 为什么 / 怎么验证 / 关联 issue**。
- 一个 PR 只做一件事；顺手重构请单独开 PR，避免 diff 混杂。

## 分支命名

- 前缀：`feat/` `fix/` `docs/` `refactor/` `chore/` `test/` `perf/` `style/`。
- 英文短横线描述，如 `feat/webui-settings`、`fix/pg-stale-pidfile`；不写日期、不写版本号。
- 永远从最新 `develop` 拉出；合并后删除本地与远程分支。

## 提交信息

采用 **Conventional Commits**，结构是 **head + 可选 body + 可选 footer**：

```
<type>(<scope>): 简短描述

- 改了什么，一两句一条
- 为什么改，必要时补一句

Refs: #123
```

- **head**：`type(scope): 描述`；`type` 只能取
  `feat` `fix` `docs` `refactor` `chore` `test` `build` `ci` `perf` `style` `revert`；
  `scope` 可选（小写字母 / 数字 / 短横线），描述用中文或英文皆可。
- **body**：head 后隔一个空行，用 `- ` 分条；只写改了什么与为什么，不写技术长文
  （踩坑与背景写进 AGENTS.md 陷阱节或 `PROGRESS.md`）。
- **footer**：body 后隔一个空行，每行 `Token: value` 或 `Token #编号`。常用：
  - `Refs: #123` —— 关联 issue / PR（不关闭）；
  - `Closes #123` —— 合并后自动关闭 issue；
  - `BREAKING CHANGE: ...` —— 不兼容变更（必须写清迁移方式）；
  - `Co-authored-by: Name <email>` —— 共同作者。
  没有可关联的内容就不写 footer，不要硬凑。
- 一次提交只做一件事；代码与文档分开提交；同一文件的改动一次改完。

## 本地验证

提交前必须通过：

```bash
bash scripts/check.sh        # ruff format --check + ruff check + mypy + pytest
```

- 改了 CLI / WebUI / 启动 / 配置：实际运行对应命令或页面，不能只看测试通过。
- 新行为补测试；修 bug 尽量补回归用例。
- 依赖真库的用例在 PG 未运行时自动 skip；跑全量前先 `uv run aris db start`。

## 文档要求

- **用户文档**：`docs/` 根目录（人类可读；后续按 `docs/zh` / `docs/en` 分语言）。
- **AI 契约文档**：`docs/forAiDoc/`（边界、接口、为什么这么设计）。
- **阶段过程文档**：`docs/process/`（阶段结束后移入 archive）。
- **状态与待办**：`PROGRESS.md` / `todolist.md`（唯一真相源）。
- 改行为要同步对应文档；纯文档改动也要核对命令、路径与链接是否仍有效。

## 发布与变更记录

- 每个版本在 `changelogs/<版本>.md` 写一条面向用户的变更记录（格式见
  `changelogs/README.md`）；未发布的改动先写进 `changelogs/unreleased.md`。
- 发版流程见 `docs/DEV-FLOW.md` 第 6 节；版本号规则见 AGENTS.md §9。
