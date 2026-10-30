"""v0.4.4 W3：模块开关（data/config/modules.toml）与依赖解析。"""

from __future__ import annotations

from pathlib import Path

import pytest

from aris.modules import (
    MODULES,
    ModulesConfig,
    load_modules,
    module_enabled,
    resolve_modules,
    set_module_enabled,
    switch_warning,
)


def _write_modules(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_are_all_enabled() -> None:
    state = resolve_modules(ModulesConfig())
    assert len(state.enabled) == len(MODULES) == 7
    assert all(state.enabled.values())
    assert state.enabled_steps() == {}
    assert state.reasons == {}


def test_disable_knowledge_cascades_to_webui() -> None:
    state = resolve_modules(ModulesConfig(), overrides={"knowledge": False})
    assert state.enabled["knowledge"] is False
    assert state.enabled["webui"] is False
    assert "依赖的模块已关闭" in state.reasons["webui"]
    steps = state.enabled_steps()
    assert "knowledge" in steps
    assert "webui" in steps
    assert "模块 knowledge 已关闭" in steps["knowledge"]


def test_disable_store_cascades_to_dependents() -> None:
    state = resolve_modules(ModulesConfig(), overrides={"store": False})
    assert state.enabled["store"] is False
    assert state.enabled["knowledge"] is False
    assert state.enabled["webui"] is False
    assert {"store.db", "store.embed"} <= set(state.enabled_steps())
    # behavior / mcp / character 不依赖 store，仍可用
    assert state.enabled["behavior"] and state.enabled["mcp"] and state.enabled["character"]


def test_disable_behavior_only_affects_itself() -> None:
    state = resolve_modules(ModulesConfig(), overrides={"behavior": False})
    assert [name for name, ok in state.enabled.items() if not ok] == ["behavior"]


def test_load_modules_reads_table(tmp_path: Path) -> None:
    path = _write_modules(
        tmp_path / "modules.toml",
        "[modules]\nknowledge = false\nvoice = false\n",
    )
    cfg = load_modules(path)
    assert cfg.knowledge is False
    assert cfg.voice is False
    assert cfg.store is True


def test_load_modules_tolerates_bad_values(tmp_path: Path) -> None:
    path = _write_modules(
        tmp_path / "modules.toml",
        "[modules]\nknowledge = 1\nunknown_module = false\n",
    )
    cfg = load_modules(path)
    assert cfg.knowledge is True  # 非布尔值忽略、按默认 true


def test_load_modules_tolerates_broken_toml(tmp_path: Path) -> None:
    path = _write_modules(tmp_path / "modules.toml", "[modules\n")
    assert load_modules(path).store is True


def test_set_module_enabled_preserves_comments(tmp_path: Path) -> None:
    path = _write_modules(
        tmp_path / "modules.toml",
        "# 头部注释\n[modules]\n# 知识库\nstore = true\nknowledge = true\n",
    )
    set_module_enabled("knowledge", False, path=path)
    text = path.read_text(encoding="utf-8")
    assert "# 头部注释" in text
    assert "# 知识库" in text
    assert "knowledge = false" in text
    assert load_modules(path).knowledge is False


def test_set_module_enabled_appends_key(tmp_path: Path) -> None:
    path = _write_modules(tmp_path / "modules.toml", "[modules]\nstore = true\n")
    set_module_enabled("voice", False, path=path)
    assert load_modules(path).voice is False
    # 已有的键没被动
    assert load_modules(path).store is True


def test_set_module_enabled_creates_file_from_seed(tmp_path: Path) -> None:
    path = tmp_path / "modules.toml"
    set_module_enabled("voice", False, path=path)
    assert path.is_file()
    assert load_modules(path).voice is False


def test_set_module_enabled_rejects_unknown(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        set_module_enabled("nope", True, path=tmp_path / "modules.toml")


def test_switch_warning_reports_cascade(tmp_path: Path, monkeypatch) -> None:
    path = _write_modules(tmp_path / "modules.toml", "[modules]\n")
    monkeypatch.setattr("aris.modules.modules_file", lambda: path)

    warning = switch_warning("knowledge", False)
    assert warning is not None
    assert "webui" in warning


def test_module_enabled_uses_dependency_cascade(tmp_path: Path, monkeypatch) -> None:
    path = _write_modules(tmp_path / "modules.toml", "[modules]\nstore = false\n")
    monkeypatch.setattr("aris.modules.modules_file", lambda: path)

    assert module_enabled("store") is False
    assert module_enabled("knowledge") is False
    assert module_enabled("behavior") is True
    assert module_enabled("unknown") is False


def test_disabled_module_steps_are_skipped_in_probe(monkeypatch) -> None:
    """serve 探针把关闭模块的步骤标 skipped（不装配、不退出）。"""
    from aris import serve as serve_module

    monkeypatch.setattr(
        serve_module, "load_modules", lambda path=None: ModulesConfig(knowledge=False)
    )
    outcomes = serve_module.probe_all()
    by_name = {outcome.step.name: outcome for outcome in outcomes}
    assert by_name["knowledge"].status == "skipped"
    assert "模块 knowledge 已关闭" in by_name["knowledge"].detail
    assert by_name["webui"].status == "skipped"
    assert "依赖的模块已关闭" in by_name["webui"].detail
