#!/usr/bin/env bash
# 发版准备（v0.4.5 定稿流程：docs/dev-flow.md §6 / docs/process/v0.4.5.md §4.1）。
#
# 渠道由分支名表达（AGENTS.md §9）：
#   正式版  release/vX.Y.Z        → 合并后打 vX.Y.Z
#   beta    release/beta-vX.Y.Z   → 合并后打 beta-vX.Y.Z
#   alpha   不走 release 分支，直接在 develop 打 alpha-vX.Y.Z（本脚本不处理）
#
# 做的事：
#   1. 校验：在 develop、工作区干净、与 upstream/develop 比对、号码未占用
#   2. 按渠道切 release/vX.Y.Z 或 release/beta-vX.Y.Z
#   3. 调 bump-version.sh 改版本号（uv lock / uv sync 由它自己跑）
#   4. 提示手工封 CHANGELOG.md 的版本段（本脚本不改文案）
#   5. 跑 release-check.sh（封版前会因 CHANGELOG 未写而 FAIL，属预期）
#   6. 打印后续命令
#
# 不做：推送、PR、打 tag、合并 main —— 全部由开发者执行。
#
# 用法：
#   bash scripts/release.sh 0.4.5            # 正式版
#   bash scripts/release.sh patch            # 正式版，0.4.4 -> 0.4.5
#   bash scripts/release.sh --beta patch     # beta 渠道
#   bash scripts/release.sh minor|major

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# shellcheck source=lib-version.sh
. "$REPO_ROOT/scripts/lib-version.sh"

VERSION_FILE="src/aris/__init__.py"

usage() {
    cat <<'EOF'
用法：bash scripts/release.sh [--beta] <版本 | patch | minor | major>

  bash scripts/release.sh 0.4.5          # 正式版：release/v0.4.5
  bash scripts/release.sh patch          # 当前版本 patch +1
  bash scripts/release.sh --beta patch   # beta：release/beta-v0.4.5
  bash scripts/release.sh minor|major    # minor / major +1

alpha 不走 release 分支（直接在 develop 打 alpha-vX.Y.Z tag），本脚本不处理。
只准备本地 release 分支；推送、PR、tag、合并 main 由开发者执行。
EOF
}

die() {
    echo "错误：$*" >&2
    exit 1
}

channel="stable"
args=()
for item in "$@"; do
    case "$item" in
    -h | --help)
        usage
        exit 0
        ;;
    --beta) channel="beta" ;;
    --alpha)
        echo "错误：alpha 不走 release 分支，直接在 develop 打 alpha-vX.Y.Z tag" >&2
        exit 2
        ;;
    -*)
        echo "错误：未知参数 $item" >&2
        usage >&2
        exit 2
        ;;
    *)
        args+=("$item")
        ;;
    esac
done

if [ ${#args[@]} -ne 1 ]; then
    usage >&2
    exit 2
fi

arg="${args[0]}"

# ---- 1. 前置校验 ----
branch="$(git symbolic-ref --short HEAD 2>/dev/null || echo '<detached>')"
[ "$branch" = "develop" ] || die "当前分支是 $branch，发版准备必须在 develop 上进行"

if [ -n "$(git status --porcelain)" ]; then
    echo "错误：工作区不干净，先提交或 stash 再发版准备：" >&2
    git status --short >&2
    exit 1
fi

current="$(sed -n 's/^__version__ *= *"\(.*\)"/\1/p' "$VERSION_FILE" | head -1)"
[ -n "$current" ] || die "$VERSION_FILE 里找不到 __version__"
cur_base="${current%.dev*}"

# 目标版本：显式给号就直接用；patch/minor/major 按当前号推算（与 bump-version.sh 同规则）
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

[[ "$base" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] ||
    die "版本号必须是 X.Y.Z 或 X.Y.Z.W（不带后缀），收到 '$base'"
[ "$base" != "$cur_base" ] || die "目标版本与当前版本相同（$cur_base）"

if existing="$(version_existing_tag "$base")"; then
    die "号码 $base 已被 tag $existing 占用（各渠道共用号码，同一号只能发布一次）"
fi
if ! version_gt "$base" "$cur_base"; then
    die "目标版本 $base 必须大于当前版本 $cur_base"
fi

# 与上游比对（只告警：fork 上领先的提交本来就要靠发版 PR 带上去）
if git remote get-url upstream >/dev/null 2>&1; then
    # 不让 fetch 卡在交互式凭据提示上
    if GIT_TERMINAL_PROMPT=0 git fetch --quiet upstream develop 2>/dev/null; then
        if git rev-parse --verify -q upstream/develop >/dev/null; then
            if [ "$(git rev-parse HEAD)" = "$(git rev-parse upstream/develop)" ]; then
                echo "[ ok ] 本地 develop 与 upstream/develop 一致"
            else
                echo "[warn] 本地 develop 与 upstream/develop 不一致（发版 PR 会把这些提交带上去，确认是有意的就行）"
            fi
        fi
    else
        echo "[warn] 无法从 upstream 拉取 develop（离线或权限问题），跳过同步比对"
    fi
else
    echo "[warn] 没有 upstream 远端，跳过同步比对"
fi

# ---- 2. 切 release 分支（渠道由分支名表达）----
if [ "$channel" = "beta" ]; then
    release_branch="release/beta-v$base"
    tag_hint="beta-v$base"
else
    release_branch="release/v$base"
    tag_hint="v$base"
fi
if git show-ref --verify --quiet "refs/heads/$release_branch"; then
    die "分支 $release_branch 已存在，先处理（删除或改名）再重试"
fi
git switch -c "$release_branch" || die "切分支 $release_branch 失败"

# ---- 3. bump ----
bash scripts/bump-version.sh "$base" || die "bump 失败，当前仍在 $release_branch"

# ---- 4. 提示封 CHANGELOG ----
today="$(date +%F)"
echo
echo "下一步：手工封 CHANGELOG.md（脚本不代写文案）——"
echo "  在 '## [Unreleased]' 段之后加："
echo "    ## [$base] - $today"
echo "    ### 亮点            # 可选，人话写 2~3 条"
echo "    ### 新增 / 改进 / 修复 / 升级注意"
echo "  然后把 [Unreleased] 里属于本版的内容搬进去（没有内容的分类直接省略）。"

# ---- 5. release-check（封版前 FAIL 属预期）----
echo
echo "==> bash scripts/release-check.sh"
bash scripts/release-check.sh
rc=$?

# ---- 6. 后续命令 ----
echo
echo "后续（全部由开发者执行）："
echo "  1. 封完 CHANGELOG 后重跑：bash scripts/release-check.sh    # 必须 PASS"
echo "  2. git add -A && git commit -m 'chore(release): $tag_hint'"
echo "  3. git push origin $release_branch"
echo "  4. 上游开 PR：$release_branch → main"
echo "  5. 在 PR 上开启原生自动合并：gh pr merge --auto --merge"
echo "     （需上游已开 Allow auto-merge，且 main 的必需检查含 check + integration）"
echo "  6. 合并后在上游 main 打 tag 并推送：$tag_hint"
echo "  7. 再开 PR：main → develop（--no-ff 合并），随后删除 $release_branch"
echo "  8. 不创建 GitHub Release（等 GUI 打包后补）"

if [ "$rc" -ne 0 ]; then
    echo
    echo "注意：上面 release-check 未通过；封完 CHANGELOG 版本段后重跑即可（封版前属预期）。"
fi
exit "$rc"
