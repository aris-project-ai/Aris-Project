# 开发流程（人类版）

> 给人看的操作顺序；规则权威仍是 `AGENTS.md`（§7 验证、§8 Git、§9 版本号、§10 文档规范）。
> AI 直接读 AGENTS.md 即可，不需要本文件。

## 0. 开工前

- 读 `PROGRESS.md`（当前状态）与 `todolist.md`（当前阶段要做什么）。
- 环境不对时先跑 `uv run aris doctor`。

## 1. 拉分支

```bash
git switch develop
git pull --ff-only
git switch -c feat/<topic>     # 前缀：feat / fix / docs / refactor / chore / perf / test
```

- 一个分支只做一件事，从最新 `develop` 拉出。
- 不直接往 `main` 提交；日常也不在 `develop` 上直提。

## 2. 写与验

- 代码改动**必须实跑**；纯文档改动不用跑测试。
- 提交前跑全检：

```bash
bash scripts/check.sh          # ruff check + format + mypy + pytest
uv run aris db start           # 需要真库的用例先起库（否则自动 skip）
uv run pytest tests/test_x.py -q
```

- 改了契约就同步对应 `docs/forAiDoc/` 文档；状态变化只改 `PROGRESS.md`。

## 3. 提交

格式：`<type>(<scope>): 简短中文描述`，type 取
`feat|fix|docs|refactor|chore|test|build|ci|perf|style|revert`。

body 空行后用 `-` 分条，每条一两句：

```
feat(knowledge): 支持 PDF 摄入

- 新增 pdf loader，复用现有分块逻辑
- 摄入失败逐条降级为 failed，不中断整批
```

- 代码与文档分开提交；同一文件的改动一次改完。
- 提交前确认没有把 `data/`、密钥、`.env` 带进去。

## 4. 合并回 develop

```bash
git switch develop
git merge --no-ff feat/<topic>
git branch -d feat/<topic>
git push origin --delete feat/<topic>
```

- 验证通过再合并；`--no-ff` 保留分支历史。
- 合并后删本地与远程 feature 分支。

## 5. 发版

```bash
bash scripts/bump-version.sh 0.4.4     # 或 patch / minor / major；只改文件不提交
# 提交版本号改动
bash scripts/release-check.sh          # 必须 PASS
git switch main
git merge --no-ff develop
git tag beta-v0.4.4                    # 或 v0.4.4；alpha 只在 develop 发 alpha-vX.Y.Z
git push origin main --tags
```

- 号码全线唯一：同一个 `X.Y.Z` 只能出现一次。
- beta 与正式版都发在 `main`；alpha 只在 `develop`。

## 6. 热修

- 从最新 `develop` 开 `fix/<topic>`，走同样流程，发 patch 版本。
- 不在 `main` 上直接改。

## 7. 换机

```bash
bash scripts/install-git-hooks.sh
git config blame.ignoreRevsFile .git-blame-ignore-revs
```

## 8. 文档放哪

- 人类文档 → `docs/`（如本文件、将来的使用手册）。
- AI 契约与约束 → `docs/forAiDoc/`；先看 AGENTS.md §10 的文档规范。
- 历史与作废方案 → `docs/archive/`。
