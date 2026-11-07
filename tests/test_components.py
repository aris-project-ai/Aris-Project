"""S1 T6：外部组件清单（版本 / 来源 / 校验值的唯一来源）。

守的是三件事：
- 平台归一只在 components.py 做，不支持的平台明确报错；
- 可下载条目必须带合法 sha256，缺校验不允许安装；
- 镜像只能换地址，不能绕过校验；清单之外不再出现版本常量。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from aris.cli import _cmd_components
from aris.infra import components as comp

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "aris"


def _ns(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


# ---------------------------------------------------------------------------
# 平台归一
# ---------------------------------------------------------------------------


def test_platform_key_maps_x86_64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comp.sys, "platform", "linux")
    monkeypatch.setattr(comp._platform, "machine", lambda: "x86_64")
    assert comp.platform_key() == "linux-64"


def test_platform_key_maps_aarch64(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comp.sys, "platform", "linux")
    monkeypatch.setattr(comp._platform, "machine", lambda: "aarch64")
    assert comp.platform_key() == "linux-aarch64"


def test_platform_key_rejects_other_os(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comp.sys, "platform", "darwin")
    with pytest.raises(comp.ComponentsError):
        comp.platform_key()


def test_platform_key_rejects_other_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(comp.sys, "platform", "linux")
    monkeypatch.setattr(comp._platform, "machine", lambda: "riscv64")
    with pytest.raises(comp.ComponentsError):
        comp.platform_key()


# ---------------------------------------------------------------------------
# 清单完整性与校验
# ---------------------------------------------------------------------------


def test_component_ids_are_unique() -> None:
    ids = [c.id for c in comp.all_components()]
    assert len(ids) == len(set(ids))


def test_archives_have_sha_for_every_supported_platform() -> None:
    for component in comp.all_components():
        if not isinstance(component, comp.Archive):
            continue
        for platform in comp.SUPPORTED_PLATFORMS:
            digest = comp.require_sha(component, platform)
            assert len(digest) == 64


def test_require_sha_rejects_missing() -> None:
    broken = comp.Archive(
        id="broken",
        version="1",
        base_url="https://example.invalid",
        files={"linux-64": "broken-linux-64"},
        sha256={},
    )
    with pytest.raises(comp.ComponentsError, match="sha256"):
        comp.require_sha(broken, "linux-64")


def test_require_sha_rejects_malformed() -> None:
    broken = comp.Archive(
        id="broken",
        version="1",
        base_url="https://example.invalid",
        files={"linux-64": "broken-linux-64"},
        sha256={"linux-64": "not-a-sha"},
    )
    with pytest.raises(comp.ComponentsError, match="格式非法"):
        comp.require_sha(broken, "linux-64")


def test_by_id_unknown_lists_available() -> None:
    with pytest.raises(comp.ComponentsError, match="micromamba"):
        comp.by_id("nope")


def test_model_revision_is_commit_not_ref() -> None:
    assert len(comp.BEKKO_A25M.revision) == 40
    assert all(ch in "0123456789abcdef" for ch in comp.BEKKO_A25M.revision)


# ---------------------------------------------------------------------------
# 镜像覆盖
# ---------------------------------------------------------------------------


def test_resolve_url_uses_official_by_default() -> None:
    url = comp.resolve_url(comp.MICROMAMBA, "linux-64")
    assert url.endswith("/micromamba-linux-64")


def test_resolve_url_mirror_directory_appends_filename() -> None:
    url = comp.resolve_url(
        comp.MICROMAMBA, "linux-aarch64", {"micromamba": "https://mirror.example/2.9.0-0/"}
    )
    assert url == "https://mirror.example/2.9.0-0/micromamba-linux-aarch64"


def test_resolve_url_exact_override_wins() -> None:
    mirrors = {
        "micromamba": "https://mirror.example/2.9.0-0",
        "micromamba.linux-64": "https://other.example/custom-file",
    }
    assert comp.resolve_url(comp.MICROMAMBA, "linux-64", mirrors) == (
        "https://other.example/custom-file"
    )


def test_resolve_url_rejects_empty_mirror() -> None:
    with pytest.raises(comp.ComponentsError):
        comp.resolve_url(comp.MICROMAMBA, "linux-64", {"micromamba": "  "})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_list_json_is_parseable(capsys: pytest.CaptureFixture[str]) -> None:
    assert _cmd_components(_ns(json=True)) == 0
    data = json.loads(capsys.readouterr().out)
    ids = {item["id"] for item in data}
    assert {"micromamba", "postgresql", "pgvector", "bekko-a25m"} <= ids


def test_cli_list_human_shows_versions(capsys: pytest.CaptureFixture[str]) -> None:
    assert _cmd_components(_ns(json=False)) == 0
    out = capsys.readouterr().out
    assert "micromamba" in out
    assert "sha256" in out
    assert comp.BEKKO_A25M.revision in out


# ---------------------------------------------------------------------------
# 收编守门：版本常量不再散落在模块里
# ---------------------------------------------------------------------------


def test_bootstrap_has_no_duplicated_component_constants() -> None:
    source = (SRC / "store" / "bootstrap.py").read_text(encoding="utf-8")
    for needle in ("micromamba-linux", "PG_VERSION =", "PGVECTOR_SPEC", "conda-forge"):
        assert needle not in source, f"bootstrap.py 里仍有版本事实：{needle}"


def test_model_identity_only_in_components() -> None:
    hits = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in SRC.rglob("*.py")
        if path.name != "components.py" and "bekko-embedding" in path.read_text(encoding="utf-8")
    ]
    assert hits == []


def test_pinned_snapshot_is_not_replaced_by_other_revision(tmp_path: Path) -> None:
    """缓存里只有别的 commit 时不拿它顶替——否则锁 revision 就失效了。"""
    from aris.store.embedding.local import LocalBekkoProvider

    provider = LocalBekkoProvider(data_dir=tmp_path)
    repo_dir = tmp_path / "models" / f"models--{comp.BEKKO_A25M.repo.replace('/', '--')}"
    other = repo_dir / "snapshots" / "deadbeef"
    other.mkdir(parents=True)
    (other / "modules.json").write_text("{}", encoding="utf-8")
    assert provider._cached_snapshot() is None

    pinned = repo_dir / "snapshots" / comp.BEKKO_A25M.revision
    pinned.mkdir()
    (pinned / "modules.json").write_text("{}", encoding="utf-8")
    assert provider._cached_snapshot() == pinned


def test_embedding_dimension_comes_from_components() -> None:
    from aris.store.embedding import local

    assert comp.BEKKO_A25M.repo == local.DEFAULT_MODEL
    assert comp.BEKKO_A25M.dimension == local.BEKKO_A25M_DIM
