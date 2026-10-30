import importlib
from pathlib import Path

from aris.infra import paths


def test_data_root_dev_tree(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='aris'\n")
    (tmp_path / "src" / "aris").mkdir(parents=True)
    (tmp_path / "src" / "aris" / "__init__.py").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ARIS_DATA_DIR", raising=False)
    importlib.reload(paths)
    assert paths.data_root() == (tmp_path / "data").resolve()


def test_data_root_env_override(tmp_path, monkeypatch):
    d = tmp_path / "custom"
    monkeypatch.setenv("ARIS_DATA_DIR", str(d))
    importlib.reload(paths)
    assert paths.data_root() == d.resolve()


def test_data_root_install_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ARIS_DATA_DIR", raising=False)
    importlib.reload(paths)
    assert paths.data_root() == (Path.home() / ".project-aris").expanduser().resolve()
