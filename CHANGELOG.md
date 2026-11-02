# 变更记录

> 面向**使用者**：写可见变化与操作影响，不写内部重构细节。
> 本文件只保留 `[Unreleased]` 与**当前最新版本**两段；历史版本在 `changelogs/<版本>.md`。
> 发版时把上一版本整段移入 `changelogs/<版本>.md`，并在本文件顶部写新版本段。

## [Unreleased]

### 新增

### 改进

### 修复

### 升级注意

## [0.4.5.1] - 2026-11-03

### 亮点

标准化收尾补丁：修好首次发版暴露的两处 CI 问题，并清掉 v0.4.5 留下的文档债；不含功能变更。

### 改进

- 新增 `ARIS_PG_SOURCE=auto|project|system`：可收窄 PostgreSQL 来源。系统 PostgreSQL 没装
  pgvector 时用 `project` 强制走项目便携实例（`ARIS_PG_BIN` 仍最高优先）。
- 发版文档修正：fork PR 的 workflow 必须先落到 base 分支；操作步骤改为网页优先，不再依赖 `gh`。
- `PROGRESS.md` / `todolist.md` 结算 v0.4.5；v1 的存量文档清理要求写入
  `docs/process/v1.0.0-prep.md`。
- 归档已废弃的 `V1.0-PLAN.md`。

### 修复

- 修 CI 里的 PostgreSQL 探针假失败：跳过条件改为运行时判断，避免在装有系统 PostgreSQL 的
  runner 上误判为「已安装」。
- CI 的 `integration` 作业固定使用项目便携 PostgreSQL，避免选中系统实例后
  `CREATE EXTENSION vector` 失败。

### 升级注意

- 无功能变更，无需迁移数据或配置。
