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

- Python 3.14+；变量 / 函数 / 类名英文，注释与 docstring 中文；行宽不超过 100。
- 公开函数 / 类写全类型标注；新代码尽量带类型。
- 运行时数据只进 `data/`，密钥只进 `data/config/secrets.toml`，两者都不入 git。

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

Refs: #123
```

标准：

- `type` 只能取：`feat` `fix` `docs` `refactor` `chore` `test` `build` `ci` `perf` `style` `revert`。
- **footer 可选**：body 后空一行，写 `Refs: #123`（关联）/ `Closes #123`（关闭）/
  `BREAKING CHANGE: ...`（不兼容）/ `Co-authored-by: ...`；没有可关联内容就不写。
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
- **推送到 fork**（`kasamorin/Aris-Project`），不要直接推上游；攒够一批再向上游
  `aris-project-ai/Aris-Project` 的 `develop` 提 PR。

## 6. 发版

先记住三条硬规则：

- **版本号只有一处**：`src/aris/__init__.py` 的 `__version__`；tag 的数字必须与它一致。
- **CHANGELOG 只留两段**：根 `CHANGELOG.md` 只保留 `[Unreleased]` 与最新版本，旧版本整段放在
  `changelogs/<版本>.md`。
- **号码全线唯一**：alpha / beta / 正式共用一条数字线，同一个 `X.Y.Z` 只能出现一次。

版本号与 CHANGELOG 由脚本一起改；**不要手工改 `__version__`，也不要手工搬 CHANGELOG 段**。

| 渠道 | 分支 / tag | 命令 |
|---|---|---|
| alpha | 直接在 `develop` 打 `alpha-vX.Y.Z` | `bash scripts/bump-version.sh <版本\|patch>` |
| beta | `release/beta-vX.Y.Z` → `main` | `bash scripts/release.sh --beta <版本\|patch>` |
| 正式版 | `release/vX.Y.Z` → `main` | `bash scripts/release.sh <版本\|patch>` |

bump 脚本会依次做：校验号码未被占用且递增 → 把上一版归档到 `changelogs/` → 把 `[Unreleased]`
切成 `## [新版本] - 今天` → 改 `__version__` → `uv lock` / `uv sync`。如果 `[Unreleased]` 是空的，
脚本会直接失败——先把本版改动写进 `[Unreleased]` 再发版。

### 6.1 alpha（开发通道，只在 develop）

```bash
git switch develop
git pull --ff-only

# 1. 把本版面向使用者的改动写进 CHANGELOG.md 的 [Unreleased]
# 2. 一条命令完成 bump + 归档 + 切段
bash scripts/bump-version.sh patch        # 或指定版本：bash scripts/bump-version.sh 0.4.7

# 3. 自检：必须 PASS
bash scripts/release-check.sh

# 4. 提交并打 tag（tag 必须指向这次 bump 提交）
git add -A
git commit -m "chore(release): 版本号 bump 至 0.4.7"
git tag alpha-v0.4.7

# 5. 推送由开发者执行
git push origin develop
git push origin alpha-v0.4.7
```

alpha 不进 `main`、不开 PR；`alpha-v*` tag 触发 `smoke` 档 CI。

### 6.2 beta / 正式版

```bash
git switch develop
git pull --ff-only

# 发版准备：切 release 分支 + bump + 归档 CHANGELOG + release-check
bash scripts/release.sh patch             # 正式版：release/vX.Y.Z
bash scripts/release.sh --beta patch      # beta：release/beta-vX.Y.Z

# 需要「亮点」就补进 CHANGELOG.md 的新版本段，然后重跑自检
bash scripts/release-check.sh             # 必须 PASS

git add -A
git commit -m "chore(release): vX.Y.Z"
git push origin release/vX.Y.Z
```

随后（以下均在网页上操作，不需要 `gh`）：

1. 在 `upstream` 开 PR：`kasamorin:release/vX.Y.Z → aris-project-ai:main`；
2. PR 页面右下 **Enable auto-merge** → 选 **Merge commit**（等价 `--no-ff`，保留分支历史）；
3. 必需检查（`check` + `integration`）全绿后自动合并；在 `upstream` 的 `main` 上打 tag 并推送
   （`vX.Y.Z` / `beta-vX.Y.Z`）；
4. 再开 PR：`main → develop`，同样开 auto-merge；
5. 删除 release 分支（本地 `git branch -d`；远端在 PR 页面点 **Delete branch**）；
6. **不创建 GitHub Release**（等 GUI 打包后补）。

> 装了 `gh` 也可以用 `gh pr merge --auto --merge`；网页操作与它完全等价。

### 6.3 发版自查（最容易漏的几项）

- `uv run aris --version` 与 tag 数字一致（tag 不能打在旧版本号上）。
- `CHANGELOG.md` 只有 `[Unreleased]` 与当前版本；`changelogs/` 里有上一版。
- `bash scripts/release-check.sh` 输出 PASS。
- tag 前缀与渠道一致：`alpha-v` / `beta-v` / `v`。
- 发版后同步 `PROGRESS.md` 的版本状态，勾掉 `todolist.md` 的对应条目。

### 6.4 约定与 CI

- 远端约定：`origin` = 日常 fork（`kasamorin/Aris-Project`），`upstream` = 上游
  （`aris-project-ai/Aris-Project`）；代码只推 `origin`，PR 开在 `upstream`。
- 渠道与分支：alpha 不走 release 分支，直接在 `develop` 打 `alpha-vX.Y.Z`；beta 用
  `release/beta-vX.Y.Z`；正式版用 `release/vX.Y.Z`。tag 与分支一一对应，号码全线唯一。
- CI 分档（`.github/workflows/ci.yml`）：
  - 普通 PR 与 `develop` / `main` 的 push → `check`（ruff / format / mypy / pytest，PG 与 embedding 用例自动 skip）；
  - PR → `main` 与 push 到 `main` → `integration`（真起便携 PostgreSQL + 下载 embedding 模型，跑全量测试与冷启动自检）；
  - `alpha-v*` tag → `smoke`（不装 embedding 组，只验 CLI 与 `serve --dry-run`）。
- 自动合并的前置设置（上游仓库，只做一次）：
  - Settings → General → Pull Requests → 勾上 **Allow auto-merge**；
  - 分支保护 / ruleset：`main` 必需检查 `check` + `integration`，`develop` 必需检查 `check`
    （仓库内的参考定义见 `.github/rulesets/`，在上游导入后生效）；
  - 被 `if` 跳过的作业按 GitHub 规则视为通过，不会卡住不相关的 PR；
  - 不强制分支保持最新（CI 跑在 PR 的合并结果上），单人开发不必反复点 Update branch；
  - **workflow 必须先落在 base 分支**：fork 发起的 PR，`pull_request` 读取的是**基线仓库
    base 分支上的** `.github/workflows/`。`main` 上还没有 workflow 时，`release → main`
    的 PR 不会触发任何作业（实测 0 run），只能先绕过保护合并一次把 workflow 带进去
    （bootstrap）；此后正常。
  - fork 发起的首个 PR，Actions 可能要求在 PR 页面点一次 **Approve and run**（首次贡献者限制）。
- 单次 patch 装不下的小功能可下探一段：`vX.Y.Z.W`（beta 线写 `beta-vX.Y.Z.W`）。
- `release.sh` 只做本地准备：校验、切分支、bump、封 CHANGELOG、跑 `release-check.sh`、打印后续命令；
  **不推送、不打 tag、不合并 `main`**。
- 变更记录：根 `CHANGELOG.md` 只留 `[Unreleased]` 与**当前最新版本**；bump 时由
  `scripts/changelog.py` 自动归档上一版并切段（格式见 `changelogs/README.md`）。

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

