#!/usr/bin/env bash
# 版本发布前检查（AGENTS.md §8 Git 流程 / §9 版本号）：
#   1. 版本号结构：唯一源是 src/aris/__init__.py；纯数字 X.Y.Z / X.Y.Z.W，
#      不带 .dev0 / -beta 等后缀；pyproject.toml 走 dynamic version
#   2. 已安装元数据与源一致（uv cache-keys 是否生效的兜底）
#   3. uv.lock 与 pyproject.toml 同步（uv lock --check）
#   4. 当前分支是 develop 或 release/*，且无未合并的本地 feature 分支
#   5. 号码未被任何渠道占用（alpha-vX.Y.Z / beta-vX.Y.Z / vX.Y.Z / 历史 vX.Y.Z-beta）
#   6. 号码大于已发布的最后一个号
#   7. CHANGELOG.md 有非空的 [<ver>] 段，且 changelogs/<ver>.md 不存在（归档只放旧版本）
# 通过则输出发布流程提示并 exit 0；否则列出问题 exit 1。
# 用法：bash scripts/release-check.sh

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 版本号规则与 bump-version.sh 共用（见 lib-version.sh）
# shellcheck source=lib-version.sh
. "$REPO_ROOT/scripts/lib-version.sh"

PYPROJECT="pyproject.toml"
VERSION_FILE="src/aris/__init__.py"

# 分发包名：唯一源是 pyproject 的 name（import 包名与命令仍是 aris，不随品牌改名）
DIST_NAME="$(python3 -c 'import sys,tomllib,pathlib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["name"])' "$PYPROJECT" 2>/dev/null || echo 'aris')"

fail=0

echo "===== 发布检查 ====="

# ---- 1. 版本号单一来源 ----
ver="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$VERSION_FILE" | head -1)"
if [[ ! "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    if [[ "$ver" == *".dev"* ]]; then
        echo "[FAIL] 版本串不再使用 .devN：beta 与正式共用纯数字版本号，渠道由 tag 表达"
    else
        echo "[FAIL] $VERSION_FILE 的版本号缺失或不合法（X.Y.Z / X.Y.Z.W，不带后缀）: '${ver:-<缺失>}'"
    fi
    fail=1
else
    echo "[ ok ] 版本唯一源 $VERSION_FILE: $ver（纯数字，渠道由 tag 决定）"
fi

if grep -qE '^version *= *"' "$PYPROJECT"; then
    echo "[FAIL] $PYPROJECT 仍有静态 version —— 版本号只能有一处，见 AGENTS.md §9"
    fail=1
elif ! grep -qE '^dynamic *= *\["version"\]' "$PYPROJECT"; then
    echo "[FAIL] $PYPROJECT 未声明 dynamic = [\"version\"]"
    fail=1
else
    echo "[ ok ] $PYPROJECT 使用 dynamic version（无第二处手写）"
fi

if ! grep -qF 'attr = "aris.__version__"' "$PYPROJECT"; then
    echo "[FAIL] $PYPROJECT 缺少 [tool.setuptools.dynamic] version = {attr = \"aris.__version__\"}"
    fail=1
fi
if ! grep -qE "^cache-keys *=.*$VERSION_FILE" "$PYPROJECT"; then
    echo "[FAIL] $PYPROJECT 缺少 [tool.uv] cache-keys 指向 $VERSION_FILE（改了版本 uv 不会重建元数据）"
    fail=1
fi

# ---- 2. 已安装元数据与源一致（venv 存在时才查）----
if [ -x ".venv/bin/python" ]; then
    installed="$(.venv/bin/python -c \
        "import importlib.metadata as m; print(m.version('$DIST_NAME'))" 2>/dev/null || echo '')"
    if [ "$installed" = "$ver" ]; then
        echo "[ ok ] 已安装元数据一致: $DIST_NAME==$installed"
    else
        echo "[FAIL] 已安装元数据 ($installed) 与 $VERSION_FILE ($ver) 不一致"
        echo "         跑一次 uv sync（或用 scripts/bump-version.sh 改版本）"
        fail=1
    fi
else
    echo "[skip] 未找到 .venv，跳过已安装元数据检查"
fi

# ---- 3. uv.lock 与 pyproject.toml 同步 ----
if lock_out="$(uv lock --check 2>&1)"; then
    echo "[ ok ] uv.lock 与 $PYPROJECT 同步"
else
    echo "[FAIL] uv.lock 不同步，跑一次 uv lock 后重试："
    printf '%s\n' "$lock_out" | sed 's/^/         /'
    fail=1
fi

# ---- 4. 分支状态 ----
cur="$(git symbolic-ref --short HEAD 2>/dev/null || echo '<detached>')"
case "$cur" in
develop | release/*) echo "[ ok ] 当前分支: $cur" ;;
*)
    echo "[FAIL] 当前分支: $cur（发布检查应在 develop 或 release/<版本> 上进行）"
    fail=1
    ;;
esac

unmerged=""
for b in $(git for-each-ref --format='%(refname:short)' refs/heads/); do
    case "$b" in
    develop | main | oldWish) continue ;;
    feat/memory-old) continue ;; # 长期保留的存档分支，不合 develop
    release/*) continue ;;       # 发版分支本身就是待合并项，不算遗漏
    esac
    if ! git merge-base --is-ancestor "$b" develop 2>/dev/null; then
        unmerged="$unmerged $b"
    fi
done
if [ -z "$unmerged" ]; then
    echo "[ ok ] 无未合并的本地 feature 分支"
else
    echo "[FAIL] 存在未合并的本地分支:$unmerged（先合并回 develop 再发布）"
    fail=1
fi

# ---- 4.5 变更记录（面向使用者，发版前必须写）----
# 规则：CHANGELOG.md 里有非空的 `## [<ver>]` 段；changelogs/<ver>.md 不得存在
# （归档目录只放旧版本，存在即说明重复归档 / 重复发布）。
CHANGELOG="CHANGELOG.md"
ARCHIVED="changelogs/${ver}.md"

changelog_section_nonempty() {
    awk -v ver="$1" '
        index($0, "## [" ver "]") == 1 { inside = 1; next }
        inside && index($0, "## ") == 1 { exit }
        inside && $0 !~ /^[[:space:]]*$/ { found = 1 }
        END { exit(found ? 0 : 1) }
    ' "$CHANGELOG"
}

if [ -z "$ver" ]; then
    echo "[skip] 版本号不可用，跳过变更记录检查"
elif [ ! -f "$CHANGELOG" ]; then
    echo "[FAIL] 缺少 $CHANGELOG（最新版本与 [Unreleased] 都在这里，发版前必须写）"
    fail=1
elif ! changelog_section_nonempty "$ver"; then
    echo "[FAIL] $CHANGELOG 里缺少非空的 '## [$ver] - YYYY-MM-DD' 段（发版前必须写）"
    fail=1
else
    echo "[ ok ] 变更记录: $CHANGELOG 的 [$ver] 段"
fi
if [ -n "$ver" ] && [ -e "$ARCHIVED" ]; then
    echo "[FAIL] $ARCHIVED 已存在（号码重复归档 / 重复发布；归档目录只放旧版本）"
    fail=1
fi

# ---- 5. 号码占用 ----
if [ -n "$ver" ]; then
    if existing="$(version_existing_tag "$ver")"; then
        echo "[FAIL] 号码 $ver 已被 tag $existing 占用（各渠道共用号码，同一号只能发布一次）"
        fail=1
    else
        echo "[ ok ] 号码 $ver 未被占用；发布时按渠道打 tag：alpha-v$ver / beta-v$ver / v$ver"
    fi

    # ---- 6. 单调递增 ----
    last="$(version_last_number)"
    if [ -n "$last" ] && ! version_gt "$ver" "$last"; then
        echo "[FAIL] 版本号 $ver 必须大于已发布的最后一个号码 $last"
        fail=1
    else
        echo "[ ok ] 版本号 $ver 大于已发布号码${last:+（当前最大 $last）}"
    fi
else
    echo "[skip] 版本号不可用，跳过 tag 检查"
fi

# ---- 7. 汇总 ----
echo
if [ "$fail" -eq 0 ]; then
    echo "结果：PASS（可进入版本发布流程）"
    echo "  1. 发版准备：bash scripts/release.sh [--beta] <版本|patch|minor|major>（从 develop 切 release 分支并 bump）"
    echo "  2. 封 CHANGELOG.md 的版本段，提交 chore(release): ..."
    echo "  3. 推送 ${cur} 到 fork（origin），向上游开 PR：${cur} → main"
    echo "  4. 在 PR 上开启原生自动合并：gh pr merge --auto --merge"
    echo "     （需上游已开 Allow auto-merge，且 main 的必需检查含 check + integration）"
    case "$cur" in
    release/beta-*) tag_hint="beta-v$ver" ;;
    release/*) tag_hint="v$ver" ;;
    *) tag_hint="alpha-v$ver（develop 专用，不进 main）" ;;
    esac
    echo "  5. 合并后在上游 main 打 tag 并推送：$tag_hint"
    echo "  6. 再开 PR：main → develop（--no-ff 合并），随后删除 release 分支"
    echo "  7. 不创建 GitHub Release（等 GUI 打包后补）"
    exit 0
fi

echo "结果：FAIL（先解决以上问题再重试）"
exit 1
