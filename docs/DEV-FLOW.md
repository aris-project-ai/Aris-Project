# 开发流程

> 按时间顺序：拉分支 → 写代码 → 本地验证 → 提交 → 合并 → 发版（含热修）。
> 每一步先写操作，再写这一步的标准。

## 1. 创建并切换分支

```bash
git switch develop
git pull --ff-only
git switch -c feat/add-knowledge-pdf
```

标准：

- 永远从最新 `develop` 拉，一个分支只做一件事。
- 前缀按改动类型选：`feat/` `fix/` `docs/` `refactor/` `chore/` `test/` `perf/` `style/`。
- 分支名用英文短横线描述，例如 `feat/webui-settings`、`fix/pg-stale-pidfile`；不写日期、不写版本号。
- `main` 不做日常开发；`develop` 也不直接提交。

## 2. 写代码

动手前可以先看 `PROGRESS.md` 快速了解进度。

标准：

- Python 3.12+；变量 / 函数 / 类名英文，注释与 docstring 中文；行宽不超过 100。
- 公开函数 / 类写全类型标注；新代码尽量带类型。
- 运行时数据只进 `data/`，密钥只进 `data/config/secrets.toml`（迁移完成前为 `.env`），两者都不入 git。

## 3. 本地验证

```bash
bash scripts/check.sh          # ruff format + ruff check + mypy + pytest
uv run pytest tests/test_x.py -q
uv run aris db start           # 依赖真库的用例需要；未启动会自动 skip
uv run aris doctor             # 环境与装配自检
uv run aris serve --dry-run    # 改启动 / 配置 / 路径时跑
```

标准：

- 提交前必须过 `scripts/check.sh`；只改了文档可以跳过测试，但要检查命令与链接。
- 影响运行时的改动必须实际运行验证：改 CLI 跑对应 `-h` 与命令，改 WebUI 起 `aris web` 看页面，改装配 / 配置跑 `serve --dry-run`。
- 新行为补测试；修 bug 尽量补回归用例。测试在 `tests/`，mock LLM / mock HTTP 在 `tests/support/`。
- 测试失败不提交，请不要用「稍后修」掩盖。

## 4. 提交

```bash
git add -A
git commit
```

提交信息格式：

```
<type>(<scope>): 简短中文描述

- 改了什么，一两句一条
- 为什么改，必要时补一句
```

标准：

- `type` 只能取：`feat` `fix` `docs` `refactor` `chore` `test` `build` `ci` `perf` `style` `revert`。
- 一次提交只做一件事，代码与文档分开提交；同一文件的改动一次改完。
- 不提交 `data/`、`.env`、密钥、构建产物。
- 仓库自带 commit-msg 与 pre-commit 钩子；换机后先跑 `bash scripts/install-git-hooks.sh`。

## 5. 合并回 develop

```bash
bash scripts/check.sh
git switch develop
git merge --no-ff feat/add-knowledge-pdf
git branch -d feat/add-knowledge-pdf
git push origin develop
git push origin --delete feat/add-knowledge-pdf
```

标准：

- 先验证再合并；合并用 `--no-ff`，保留分支历史。
- 合并后删本地与远程 feature 分支。
- 合并冲突尽量不要用「强制覆盖」解决。

## 6. 发版

```bash
bash scripts/bump-version.sh 0.4.4      # 或 patch / minor / major；只改文件不提交
git add -A && git commit -m "chore(release): 版本号 bump 至 0.4.4"
bash scripts/release-check.sh           # 必须 PASS
git switch main
git merge --no-ff develop
git tag beta-v0.4.4                     # 或 v0.4.4；alpha 只在 develop 发 alpha-vX.Y.Z
git push origin main --tags
```

标准：

- 渠道：beta（小版本，发 `main`）、正式版（发 `main`）、alpha（只发 `develop`）。
- 号码全线唯一：同一个 `X.Y.Z` 只能出现一次；beta 与正式共用数字线，另一个渠道要用更高的号。
- 单次 patch 装不下的小功能可下探一段：`vX.Y.Z.W`（beta 线写 `beta-vX.Y.Z.W`）。
- 发版后同步 `PROGRESS.md` 的版本状态。

## 7. 热修

```bash
git switch develop
git switch -c fix/crash-on-empty-config
# 修复、验证、提交
git switch develop && git merge --no-ff fix/crash-on-empty-config
git branch -d fix/crash-on-empty-config
```

标准：

- 热修也从最新 `develop` 拉，走与普通改动相同的验证与合并流程。
- 修复后发 patch 版本；不在 `main` 上直接改。

