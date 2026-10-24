#!/usr/bin/env bash
# 版本号 → tag 名的唯一实现（AGENTS.md §9）。
#
# 两类版本，**都发布在 main**：
#   dev 开发时版  tag beta-vX.Y.Z   __version__ X.Y.Z.dev0
#   rel 正式版    tag vX.Y.Z        __version__ X.Y.Z
#
# 密集发布、单个 patch 装不下的小功能可下探一段：X.Y.Z.W（beta 线为 beta-vX.Y.Z.W）。
# bump-version.sh 与 release-check.sh 都 source 本文件，同一规则不写两遍。

# 由版本号判断种类：dev / rel（无法识别时返回 1）
version_kind() {
    case "$1" in
    *.dev[0-9]*) printf 'dev\n' ;;
    *b[0-9]*) return 1 ;; # 旧候选版（vX.Y.ZbN）已作废，不再识别
    [0-9]*.[0-9]*.[0-9]*) printf 'rel\n' ;;
    *) return 1 ;;
    esac
}

# 版本号 → tag 名
version_to_tag() {
    local v="$1" kind
    kind="$(version_kind "$v")" || return 1
    case "$kind" in
    dev) printf 'beta-v%s\n' "${v%.dev*}" ;;
    *) printf 'v%s\n' "$v" ;;
    esac
}

# 该版本应发布在哪个分支（两类都进 main）
version_branch() {
    printf 'main\n'
}

# 该版本的 tag 是否已被占用：命中则打印 tag 名并返回 0，未命中返回 1
version_existing_tag() {
    local tag
    tag="$(git tag -l "$(version_to_tag "$1")" | head -1)"
    [ -n "$tag" ] || return 1
    printf '%s\n' "$tag"
}
