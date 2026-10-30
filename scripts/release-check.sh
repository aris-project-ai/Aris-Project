#!/usr/bin/env bash
# 版本发布前检查（AGENTS.md §8 Git 流程 / §9 版本号）：
#   1. 版本号结构：唯一源是 src/aris/__init__.py；纯数字 X.Y.Z / X.Y.Z.W，
#      不带 .dev0 / -beta 等后缀；pyproject.toml 走 dynamic version
#   2. 已安装元数据与源一致（uv cache-keys 是否生效的兜底）
#   3. uv.lock 与 pyproject.toml 同步（uv lock --check）
#   4. 当前分支是 develop 且无未合并的本地 feature 分支
#   5. 号码未被任何渠道占用（beta-vX.Y.Z / vX.Y.Z / 历史 vX.Y.Z-beta）
#   6. 号码大于已发布的最后一个号
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
if [ "$cur" = "develop" ]; then
    echo "[ ok ] 当前分支: develop"
else
    echo "[FAIL] 当前分支: $cur（发布检查应在 develop 上进行）"
    fail=1
fi

unmerged=""
for b in $(git for-each-ref --format='%(refname:short)' refs/heads/); do
    case "$b" in
    develop | main | oldWish) continue ;;
    feat/memory-old) continue ;; # 长期保留的存档分支，不合 develop
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

# ---- 5. 号码占用 ----
if [ -n "$ver" ]; then
    if existing="$(version_existing_tag "$ver")"; then
        echo "[FAIL] 号码 $ver 已被 tag $existing 占用（beta 与正式共用号码，同一号只能发布一次）"
        fail=1
    else
        echo "[ ok ] 号码 $ver 未被占用；发布时二选一：beta-v$ver / v$ver"
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
    echo "  1. 在 develop 上 bump：bash scripts/bump-version.sh <版本|patch|minor|major>"
    echo "  2. 提交 chore(release) 后合并回 main（git merge --no-ff）"
    echo "  3. 二选一打 tag：git tag beta-v$ver（beta：小版本更新）/ git tag v$ver（正式版）"
    echo "  4. git push origin develop main && git push origin <tag>"
    exit 0
fi

echo "结果：FAIL（先解决以上问题再重试）"
exit 1
