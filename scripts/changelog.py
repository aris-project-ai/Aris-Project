#!/usr/bin/env python3
"""CHANGELOG 封版助手。

把一个版本的变更记录从 `[Unreleased]` 切出来，并把上一版整段归档到
`changelogs/<版本>.md`（同时更新索引）。只改文件，不提交、不打 tag。

用法：
    python3 scripts/changelog.py cut 0.4.7
    python3 scripts/changelog.py cut 0.4.7 --date 2026-11-08

规则（AGENTS.md §9）：
    - 根 `CHANGELOG.md` 只保留 `[Unreleased]` 与**当前最新版本**两段；
    - 旧版本一个版本一个文件，文件名为纯数字版本号；
    - `[Unreleased]` 必须有实际内容，否则拒绝封版。
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
ARCHIVE_DIR = REPO_ROOT / "changelogs"
INDEX = ARCHIVE_DIR / "README.md"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")
HEADING_RE = re.compile(r"^## \[([^\]]+)\](?: - (.+))?$")

UNRELEASED_TEMPLATE = """## [Unreleased]

### 新增

### 改进

### 修复

### 升级注意
"""


@dataclass
class Section:
    """CHANGELOG 里的一个 `## [...]` 段。"""

    heading: str
    name: str
    date: str
    body: list[str]


def die(message: str) -> NoReturn:
    """打印错误并退出，保证失败时不留下半成品。"""
    print(f"错误：{message}", file=sys.stderr)
    raise SystemExit(1)


def parse(text: str) -> tuple[list[str], list[Section]]:
    """拆出文件头与所有 `## [...]` 段。"""
    lines = text.splitlines()
    heading_indexes = [i for i, line in enumerate(lines) if line.startswith("## [")]
    if not heading_indexes:
        die("CHANGELOG.md 里找不到任何 '## [...]' 段")

    preamble = lines[: heading_indexes[0]]
    sections: list[Section] = []
    for n, index in enumerate(heading_indexes):
        end = heading_indexes[n + 1] if n + 1 < len(heading_indexes) else len(lines)
        heading = lines[index]
        match = HEADING_RE.match(heading)
        if match is None:
            die(f"无法解析段标题：{heading}")
        sections.append(
            Section(
                heading=heading,
                name=match.group(1),
                date=(match.group(2) or "").strip(),
                body=lines[index + 1 : end],
            )
        )
    return preamble, sections


def trimmed(lines: list[str]) -> list[str]:
    """去掉首尾空行。"""
    result = list(lines)
    while result and not result[0].strip():
        result.pop(0)
    while result and not result[-1].strip():
        result.pop()
    return result


def has_content(lines: list[str]) -> bool:
    """段里是否有实际正文（只看非标题行）。"""
    return any(line.strip() and not line.strip().startswith("#") for line in lines)


def write_archive(section: Section) -> Path:
    """把一个旧版本整段写入 changelogs/<版本>.md。"""
    ARCHIVE_DIR.mkdir(exist_ok=True)
    path = ARCHIVE_DIR / f"{section.name}.md"
    if path.exists():
        die(f"{path.relative_to(REPO_ROOT)} 已存在（号码重复归档 / 重复发布）")

    body = trimmed(section.body)
    content = section.heading + "\n"
    if body:
        content += "\n" + "\n".join(body) + "\n"
    path.write_text(content, encoding="utf-8")
    return path


def update_index(version: str, date: str) -> None:
    """把新归档的版本插到 changelogs/README.md 索引最前面。"""
    if not INDEX.exists():
        print("提示：未找到 changelogs/README.md，跳过索引更新")
        return

    lines = INDEX.read_text(encoding="utf-8").splitlines()
    try:
        start = lines.index("## 索引")
    except ValueError:
        print("提示：changelogs/README.md 里没有 '## 索引'，跳过索引更新")
        return

    entry = f"- [`{version}`](./{version}.md)"
    if date:
        entry += f" - {date}"

    insert_at: int | None = None
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            break
        if lines[i].startswith("- ["):
            insert_at = i
            break

    if insert_at is None:
        insert_at = start + 1
        if insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
        lines[insert_at:insert_at] = [entry, ""]
    else:
        lines.insert(insert_at, entry)

    INDEX.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cut(version: str, date: str) -> None:
    """把 [Unreleased] 切成指定版本，并归档上一版。"""
    if not VERSION_RE.match(version):
        die(f"版本号必须是 X.Y.Z 或 X.Y.Z.W（纯数字），收到 '{version}'")
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        die(f"日期必须是 YYYY-MM-DD，收到 '{date}'")

    if not CHANGELOG.exists():
        die("缺少 CHANGELOG.md")
    preamble, sections = parse(CHANGELOG.read_text(encoding="utf-8"))

    unreleased = next((section for section in sections if section.name == "Unreleased"), None)
    if unreleased is None:
        die("CHANGELOG.md 里找不到 '## [Unreleased]' 段")
    if not has_content(unreleased.body):
        die("[Unreleased] 没有实际内容，先把本版改动写进去再封版")

    others = [section for section in sections if section.name != "Unreleased"]
    if len(others) > 1:
        names = "、".join(section.name for section in others)
        die(f"CHANGELOG.md 里有多个历史版本段（{names}）；先把旧版本移入 changelogs/")
    if others and others[0].name == version:
        die(f"[{version}] 段已存在，不能重复封版")

    archived = write_archive(others[0]) if others else None

    body = trimmed(unreleased.body)
    parts = [
        "\n".join(preamble).rstrip(),
        UNRELEASED_TEMPLATE.rstrip(),
        f"## [{version}] - {date}\n\n" + "\n".join(body),
    ]
    CHANGELOG.write_text("\n\n".join(parts) + "\n", encoding="utf-8")

    if archived is not None:
        update_index(others[0].name, others[0].date)
        print(f"已归档上一版：{archived.relative_to(REPO_ROOT)}")
    print(f"已封版：CHANGELOG.md 新增 '## [{version}] - {date}'，[Unreleased] 已重置")
    print("提示：需要「亮点」的话，现在补到新版本段；旧版本索引摘要也可手工补写。")


def main(argv: list[str] | None = None) -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(
        description="CHANGELOG 封版助手：归档上一版，并把 [Unreleased] 切成新版本段。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    cut_parser = subparsers.add_parser("cut", help="把 [Unreleased] 切成指定版本")
    cut_parser.add_argument("version", help="新版本号（X.Y.Z 或 X.Y.Z.W）")
    cut_parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="版本段日期（YYYY-MM-DD，默认今天）",
    )

    args = parser.parse_args(argv)
    if args.command == "cut":
        cut(args.version, args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
