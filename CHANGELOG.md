# 变更记录

> 面向**使用者**：写可见变化与操作影响，不写内部重构细节。
> 本文件只保留 `[Unreleased]` 与**当前最新版本**两段；历史版本在 `changelogs/<版本>.md`。
> 发版时把上一版本整段移入 `changelogs/<版本>.md`，并在本文件顶部写新版本段。

## [Unreleased]

### 新增

### 改进

### 修复

### 升级注意

## [0.4.5] - 2026-11-01

### 亮点

第一次按标准流程发版的版本：变更记录、CI 与发版脚本在这里定型。

### 新增

- 仓库 CI：PR 与 `develop` / `main` 推送自动跑 ruff / mypy / 单测；发版 PR 额外起真 PostgreSQL
  与 embedding 跑全量测试；alpha tag 跑轻量启动自检。
- `NOTICE`：第三方依赖许可与设计参考项目（AstrBot、AIRI 等）。
- `scripts/release.sh`：一条命令完成发版准备（校验、切分支、bump、检查），不推送、不打 tag。

### 改进

- 变更记录改为根 `CHANGELOG.md` 只留最新版本，旧版本归档到 `changelogs/`。
- README 重整：快速开始、数据与备份、参与方式更清楚，补版本与 Python 徽章。
- 发版流程定稿：`release/` 分支单一 PR → 原生 auto-merge → tag → `main` 回合并 `develop`。

### 升级注意

- 运行环境要求提高到 **Python 3.14+**（`requires-python = ">=3.14"`），旧版 Python 无法安装。
