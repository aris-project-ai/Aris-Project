#!/usr/bin/env bash
# 版本号规则（AGENTS.md §9），bump-version.sh 与 release-check.sh 共用。
#
# 版本串：X.Y.Z / X.Y.Z.W，纯数字，不带 .dev0 / -beta 等后缀。
# 渠道只由 tag 表达：
#   beta（小版本更新）  beta-vX.Y.Z
#   正式版              vX.Y.Z
#   alpha（预发布）     alpha-vX.Y.Z（只在 develop；同样占用号码）
# 号码全线唯一：同一个 X.Y.Z 只能有一个 tag（各形态合计，含历史 vX.Y.Z-beta）。
# beta / 正式发布在 main；alpha 只在 develop 预发布。

# 某号码的全部候选 tag（含历史旧形态）；参数是纯数字版本串。
# 命中则打印第一个已存在的 tag 并返回 0；未命中返回 1。
version_existing_tag() {
    local tags
    tags="$(git tag -l "beta-v$1" "v$1" "alpha-v$1" "v$1-beta")"
    [ -n "$tags" ] || return 1
    printf '%s\n' "${tags%%$'\n'*}"
}

# 已发布的最大号码；没有可用 tag 时输出空串并返回 0。
version_last_number() {
    local tag ver last=""
    for tag in $(git tag -l 'v*' 'beta-v*' 'alpha-v*'); do
        ver="${tag#beta-v}"
        ver="${ver#alpha-v}"
        ver="${ver#v}"
        ver="${ver%-beta}"
        [[ "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || continue
        if [ -z "$last" ] || version_gt "$ver" "$last"; then
            last="$ver"
        fi
    done
    [ -n "$last" ] && printf '%s\n' "$last"
    return 0
}

# $1 > $2 返回 0；相等或更小返回 1。
# 纯 bash 实现，不依赖 sort -V（Termux 的 toybox 不一定支持）。
version_gt() {
    local IFS=.
    local -a a b
    read -r -a a <<<"$1"
    read -r -a b <<<"$2"
    local i x y
    for i in 0 1 2 3; do
        x="${a[i]:-0}"
        y="${b[i]:-0}"
        if [ "$x" -gt "$y" ]; then return 0; fi
        if [ "$x" -lt "$y" ]; then return 1; fi
    done
    return 1
}
