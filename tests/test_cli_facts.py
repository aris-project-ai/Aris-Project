"""v0.4.4 W3：CLI 事实入口（aris info / config / modules）。

直接调命令函数（argparse 层另有 `-h` 覆盖），验证只读输出与开关写盘。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aris.cli import _cmd_config, _cmd_info, _cmd_modules
from aris.infra.modules import load_modules


def _ns(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def test_info_prints_environment_facts(capsys) -> None:
    assert _cmd_info(_ns()) == 0
    out = capsys.readouterr().out
    assert "Aris " in out
    assert "数据目录:" in out
    assert "配置目录:" in out
    assert "模块: 启用" in out


def test_config_validate_passes(capsys) -> None:
    assert _cmd_config(_ns(config_command="validate")) == 0
    assert "全部通过" in capsys.readouterr().out


def test_config_path_lists_all_files(capsys) -> None:
    assert _cmd_config(_ns(config_command="path")) == 0
    out = capsys.readouterr().out
    assert "modules.toml" in out
    assert "secrets.toml" in out


def test_config_list_shows_sources(capsys) -> None:
    assert _cmd_config(_ns(config_command="list")) == 0
    out = capsys.readouterr().out
    assert "用户" in out or "种子" in out


def test_config_show_masks_secrets(tmp_path: Path, monkeypatch, capsys) -> None:
    from aris.infra import paths

    (tmp_path / "secrets.toml").write_text(
        'DEEPSEEK_API_KEY = "sk-real-secret"\nWEBUI_PASSWORD = "pw"\n', encoding="utf-8"
    )
    monkeypatch.setattr(paths, "config_dir", lambda: tmp_path)

    assert _cmd_config(_ns(config_command="show", name="secrets")) == 0
    out = capsys.readouterr().out
    assert "***" in out
    assert "sk-real-secret" not in out
    assert "pw" not in out.split("WEBUI_PASSWORD")[1]


def test_config_show_accepts_name_without_suffix(capsys) -> None:
    assert _cmd_config(_ns(config_command="show", name="modules")) == 0
    assert "[modules]" in capsys.readouterr().out


def test_config_env_prints_aris_variables(capsys) -> None:
    assert _cmd_config(_ns(config_command="env")) == 0
    out = capsys.readouterr().out
    assert "ARIS_DATA_DIR=" in out
    assert "ARIS_LOG_LEVEL=" in out


def test_modules_list_shows_every_module(capsys) -> None:
    assert _cmd_modules(_ns(modules_command="list")) == 0
    out = capsys.readouterr().out
    for name in ("store", "knowledge", "mcp", "behavior", "webui", "character", "voice"):
        assert name in out


def test_modules_status_reports_enabled(capsys) -> None:
    assert _cmd_modules(_ns(modules_command="status")) == 0
    assert "启用" in capsys.readouterr().out


def test_modules_enable_disable_roundtrip(tmp_path: Path, monkeypatch) -> None:
    from aris.infra import modules as modules_module

    path = tmp_path / "modules.toml"
    path.write_text("[modules]\n", encoding="utf-8")
    monkeypatch.setattr(modules_module, "modules_file", lambda: path)

    assert _cmd_modules(_ns(modules_command="disable", name="voice")) == 0
    assert load_modules(path).voice is False

    assert _cmd_modules(_ns(modules_command="enable", name="voice")) == 0
    assert load_modules(path).voice is True
