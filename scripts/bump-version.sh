#!/usr/bin/env bash
# 版本号 bump（AGENTS.md §9）：
#   版本号唯一源是 src/aris/__init__.py 的 __version__，本脚本是唯一的改法。
#   pyproject.toml 用 dynamic version 从该文件读取，uv.lock 不记录本项目版本。
#
# 用法（两类，规则见 scripts/lib-version.sh）：
#   bash scripts/bump-version.sh dev  1.0.1    # 开发时版 → 1.0.1.dev0    tag beta-v1.0.1（合 main）
#   bash scripts/bump-version.sh rel  1.1.0    # 正式版  → 1.1.0          tag v1.1.0（合 main）
#   bash scripts/bump-version.sh rel  1.0.1.2  # 小功能可下探一段（也允许 beta-v1.0.1.2）
#   bash scripts/bump-version.sh rel  minor    # 正式版号也可用 patch|minor|major 推算
#
# 只改文件、不提交；跑完后按脚本打印的后续步骤走。

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=lib-version.sh
. "$REPO_ROOT/scripts/lib-version.sh"

VERSION_FILE="src/aris/__init__.py"

if [ $# -ne 2 ]; then
    echo "用法：bash scripts/bump-version.sh <dev|rel> <版本 | patch | minor | major>" >&2
    exit 2
fi
kind="$1"; arg="$2"
case "$kind" in
dev | rel) ;;
*)
    echo "错误：种类必须是 dev | rel，收到 '$kind'" >&2
    exit 2
    ;;
esac

current="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$VERSION_FILE" | head -1)"
if [ -z "$current" ]; then
    echo "错误：$VERSION_FILE 里找不到 __version__" >&2
    exit 1
fi
# 当前版本的基础号（去掉 .devN 后缀）
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

if ! printf '%s' "$base" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$'; then
    echo "错误：基础版本号必须是 X.Y.Z 或 X.Y.Z.W 形式，收到 '$base'" >&2
    exit 2
fi

# 组出目标 __version__（必须是 setuptools 能解析的 PEP 440）
case "$kind" in
dev) new="$base.dev0" ;;
rel) new="$base" ;;
esac

if [ "$new" = "$current" ]; then
    echo "错误：新版本与当前版本相同（$current）" >&2
    exit 2
fi

# bump 一律在干净的 develop 上做（tag 落哪个分支由种类决定）
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
if existing="$(version_existing_tag "$new")"; then
    echo "错误：tag $existing 已存在，不能重复发布" >&2
    exit 1
fi

sed -i "s/^__version__ *= *\"$current\"/__version__ = \"$new\"/" "$VERSION_FILE"
echo "版本号 $current -> $new（$VERSION_FILE，种类 $kind）"

uv lock
uv sync

tag="$(version_to_tag "$new")"
target="$(version_branch "$new")"
echo
echo "完成，当前版本：$(uv run aris --version)"
echo "下一步（tag $tag 发在 $target）："
echo "  1. git add $VERSION_FILE uv.lock && git commit -m 'chore(release): 版本号 bump 至 $new'"
echo "  2. bash scripts/release-check.sh"
echo "  3. git checkout main && git merge --no-ff develop -m 'chore(release): $tag —— <一句话总结>'"
echo "  4. git tag $tag && git push origin develop main && git push origin $tag"
