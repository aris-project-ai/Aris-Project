#!/usr/bin/env bash
# 版本号 bump（AGENTS.md §9）：
#   版本号唯一源是 src/aris/__init__.py 的 __version__，本脚本是唯一的改法。
#   版本串只写数字（X.Y.Z / X.Y.Z.W），beta / 正式由发布时的 tag 决定。
#
# 用法：
#   bash scripts/bump-version.sh 1.0.0     # 指定版本
#   bash scripts/bump-version.sh 1.0.1.2   # 小功能可下探一段
#   bash scripts/bump-version.sh patch     # 1.0.0 -> 1.0.1
#   bash scripts/bump-version.sh minor     # 1.0.1 -> 1.1.0
#   bash scripts/bump-version.sh major     # 1.1.0 -> 2.0.0
#
# 只改文件、不提交；跑完后按脚本打印的后续步骤走。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=lib-version.sh
. "$REPO_ROOT/scripts/lib-version.sh"

VERSION_FILE="src/aris/__init__.py"

if [ $# -ne 1 ]; then
    echo "用法：bash scripts/bump-version.sh <版本 | patch | minor | major>" >&2
    exit 2
fi

arg="$1"

current="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$VERSION_FILE" | head -1)"
if [ -z "$current" ]; then
    echo "错误：$VERSION_FILE 里找不到 __version__" >&2
    exit 1
fi
# 兼容旧口径：当前若是 X.Y.Z.devN，按基础号比较
cur_base="${current%.dev*}"

case "$arg" in
patch | minor | major)
    IFS=. read -r cur_major cur_minor cur_patch _ <<<"$cur_base"
    case "$arg" in
    patch) cur_patch=$((cur_patch + 1)) ;;
    minor) cur_minor=$((cur_minor + 1)); cur_patch=0 ;;
    major) cur_major=$((cur_major + 1)); cur_minor=0; cur_patch=0 ;;
    esac
    base="$cur_major.$cur_minor.$cur_patch"
    ;;
*) base="$arg" ;;
esac

if [[ ! "$base" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo "错误：版本号必须是 X.Y.Z 或 X.Y.Z.W（不带 .dev0 / -beta 等后缀），收到 '$base'" >&2
    exit 2
fi

if [ "$base" = "$cur_base" ]; then
    echo "错误：新版本与当前版本相同（$cur_base）" >&2
    exit 2
fi

# bump 一律在干净的 develop 上做
branch="$(git symbolic-ref --short HEAD 2>/dev/null || echo '<detached>')"
if [ "$branch" != "develop" ]; then
    echo "错误：当前分支是 $branch，版本 bump 必须在 develop 上进行" >&2
    exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo "错误：工作区不干净，先提交或 stash 再 bump" >&2
    git status --short >&2
    exit 1
fi

# 号码未被任何渠道占用（先查重，报错更直接）
if existing="$(version_existing_tag "$base")"; then
    echo "错误：号码 $base 已被 tag $existing 占用" >&2
    echo "      beta 与正式共用号码，同一个号只能发布一次；请换一个更高的号" >&2
    exit 1
fi

# 单调递增：新号必须大于当前号与已发布最大号中的较大者
floor="$cur_base"
last="$(version_last_number)"
if [ -n "$last" ] && version_gt "$last" "$floor"; then
    floor="$last"
fi
if ! version_gt "$base" "$floor"; then
    echo "错误：新版本 $base 必须大于当前/已发布的最大号 $floor" >&2
    exit 1
fi

sed -i "s/^__version__ *= *\"$current\"/__version__ = \"$base\"/" "$VERSION_FILE"
echo "版本号 $current -> $base（$VERSION_FILE）"

uv lock
uv sync

echo
echo "完成，当前版本：$(uv run aris --version)"
echo "下一步："
echo "  1. git add $VERSION_FILE uv.lock && git commit -m 'chore(release): 版本号 bump 至 $base'"
echo "  2. bash scripts/release-check.sh"
echo "  3. git checkout main && git merge --no-ff develop -m 'chore(release): <一句话总结>'"
echo "  4. 二选一打 tag："
echo "       git tag beta-v$base   # beta：小版本更新"
echo "       git tag v$base        # 正式版"
echo "  5. git push origin develop main && git push origin <tag>"
