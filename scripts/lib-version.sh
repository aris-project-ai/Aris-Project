#!/usr/bin/env bash
# 版本号 → tag 名的唯一实现（AGENTS.md「版本号更新」）。
#
# 三类版本（2026-10-01 定案；旧「0.x 全段为 beta / tag 带 -beta 后缀」作废）：
#   dev  开发时版  tag beta-vX.Y.Z   __version__ X.Y.Z.dev0   发布在 main
#   cand 候选/测试 tag vX.Y.ZbN      __version__ X.Y.ZbN      发布在 develop（不合 main）
#   rel  正式版    tag vX.Y.Z        __version__ X.Y.Z        发布在 main
#
# 数字共用一条版本线：dev 消耗掉的数字不再有对应正式版；正式版发版时直接给出目标号。
# bump-version.sh 与 release-check.sh 都 source 本文件，同一规则不写两遍。

# 由版本号判断种类：dev / cand / rel（无法识别时返回 1）
version_kind() {
    case "$1" in
    *.dev[0-9]*) printf 'dev\n' ;;
    *b[0-9]*) printf 'cand\n' ;;
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

# 该版本应发布在哪个分支
version_branch() {
    case "$(version_kind "$1")" in
    cand) printf 'develop\n' ;;
    *) printf 'main\n' ;;
    esac
}

# 该版本的 tag 是否已被占用：命中则打印 tag 名并返回 0，未命中返回 1
version_existing_tag() {
    local tag
    tag="$(git tag -l "$(version_to_tag "$1")" | head -1)"
    [ -n "$tag" ] || return 1
    printf '%s\n' "$tag"
}
