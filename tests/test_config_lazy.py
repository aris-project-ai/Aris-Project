import importlib


def test_data_dir_resolves_at_construction(tmp_path, monkeypatch):
    """data_dir 必须在 Settings 实例化时求值，而不是 import 时。"""
    monkeypatch.setenv("ARIS_DATA_DIR", str(tmp_path / "late"))
    from aris.infra import settings as cfg

    importlib.reload(cfg)
    s = cfg.Settings()
    assert s.data_dir == (tmp_path / "late").resolve()


def test_get_settings_uses_late_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARIS_DATA_DIR", str(tmp_path / "late2"))
    from aris.infra import settings as cfg

    importlib.reload(cfg)
    cfg.get_settings.cache_clear()
    s = cfg.get_settings()
    assert s.data_dir == (tmp_path / "late2").resolve()


def test_settings_data_dir_default_dev_tree(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='aris'\n")
    (tmp_path / "src" / "aris").mkdir(parents=True)
    (tmp_path / "src" / "aris" / "__init__.py").write_text("")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ARIS_DATA_DIR", raising=False)
    from aris.infra import settings as cfg

    importlib.reload(cfg)
    s = cfg.Settings()
    assert s.data_dir == (tmp_path / "data").resolve()
