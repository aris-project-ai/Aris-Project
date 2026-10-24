"""可迁移性与启动幂等（D14）测试：角色对齐 / 端口探测 / 二进制可运行 / data 分层。

**无外部依赖**：不连数据库、不启动实例；需要真实 PG 二进制的那条用 skipif 跳过。
设计依据见 docs/forAiDoc/PORTABILITY-AND-SINGLE-SESSION.md 与 V1.0-PLAN.md 的 M0。
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from aris.datadir import CARRIED_PATHS, ensure_dirs, missing_carried
from aris.store import pgenv
from aris.store.bootstrap import choose_port, probe_runnable
from aris.store.pgenv import (
    DEFAULT_USER,
    detect,
    ownership_error,
    port_available,
    read_role_marker,
    remember_port,
    socket_port,
    write_role_marker,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """清掉影响探针的环境变量，并复位进程内的临时端口（避免用例互相污染）。"""
    for key in ("ARIS_PG_BIN", "ARIS_PG_DSN", "ARIS_PG_PORT", "ARIS_PG_USER", "ARIS_PG_DB"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("aris.store.pgenv.shutil.which", lambda _name: None)
    remember_port(None)
    yield
    remember_port(None)


def _init_cluster(pgdata: Path) -> None:
    """造一个「已 initdb」的数据目录（只要 PG_VERSION 在，就算已初始化）。"""
    pgdata.mkdir(parents=True, exist_ok=True)
    (pgdata / "PG_VERSION").write_text("17\n", encoding="utf-8")


# ---------------------------------------------------------------- data/ 分层


def test_ensure_dirs_is_idempotent(tmp_path):
    """必须带的目录第一次建、第二次无新建（启动幂等）。"""
    assert ensure_dirs(tmp_path) == ["characters", "skills", "autorun"]
    for rel in ("characters", "skills", "autorun"):
        assert (tmp_path / rel).is_dir()
    assert ensure_dirs(tmp_path) == []


def test_missing_carried(tmp_path):
    """缺失项按「必须带」清单报出来，建齐后为空。"""
    assert missing_carried(tmp_path) == list(CARRIED_PATHS)
    for rel in CARRIED_PATHS:
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    assert missing_carried(tmp_path) == []


# ---------------------------------------------------------------- 角色对齐


def test_new_cluster_uses_host_independent_user(tmp_path):
    """新建集群的角色名与主机无关（D14 缺口②的前提）。"""
    env = detect(tmp_path / "data")

    assert env.user == DEFAULT_USER == "aris"


def test_existing_cluster_without_marker_falls_back_to_host_user(tmp_path, monkeypatch):
    """老集群（initdb -U $USER 建的）没有标记时先按宿主用户名试，行为与历史一致。"""
    monkeypatch.setenv("USER", "someone")
    data = tmp_path / "data"
    _init_cluster(data / "pgdata")

    assert detect(data).user == "someone"


def test_role_marker_roundtrip_and_precedence(tmp_path, monkeypatch):
    """标记文件优先于宿主用户名；ARIS_PG_USER 又优先于标记。"""
    data = tmp_path / "data"
    pgdata = data / "pgdata"
    _init_cluster(pgdata)
    monkeypatch.setenv("USER", "someone")

    write_role_marker(pgdata, "legacy_admin")
    assert read_role_marker(pgdata) == "legacy_admin"
    assert detect(data).user == "legacy_admin"

    monkeypatch.setenv("ARIS_PG_USER", "explicit")
    assert detect(data).user == "explicit"


# ---------------------------------------------------------------- 端口


def test_socket_port_discovery(tmp_path):
    """运行中实例的真实端口从 unix socket 文件名反推（端口不入库的落地方式）。"""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / ".s.PGSQL.60001").touch()
    assert socket_port(run_dir) == 60001
    assert socket_port(tmp_path / "nope") is None

    data = tmp_path / "data"
    _init_cluster(data / "pgdata")
    (data / "pg" / "run").mkdir(parents=True)
    (data / "pg" / "run" / ".s.PGSQL.60002").touch()
    assert detect(data).port == 60002


def test_env_port_beats_socket(tmp_path, monkeypatch):
    """ARIS_PG_PORT 显式指定时最优先。"""
    data = tmp_path / "data"
    (data / "pg" / "run").mkdir(parents=True)
    (data / "pg" / "run" / ".s.PGSQL.60002").touch()
    monkeypatch.setenv("ARIS_PG_PORT", "60003")

    assert detect(data).port == 60003


def test_choose_port_switches_when_busy(tmp_path):
    """端口被占时换一个可用端口，且不写任何配置文件。"""
    data = tmp_path / "data"
    _init_cluster(data / "pgdata")
    env = detect(data)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        taken = busy.getsockname()[1]

        assert port_available(taken) is False
        chosen = choose_port(env.with_port(taken))

    assert chosen.port != taken
    assert port_available(chosen.port) is True
    # 端口只在运行期算：换过端口后 detect() 也认这个值（本轮运行内一致）
    assert detect(data).port == chosen.port


def test_choose_port_keeps_free_port(tmp_path):
    """端口空闲时原样保留。"""
    data = tmp_path / "data"
    _init_cluster(data / "pgdata")
    env = detect(data)
    free = pgenv.free_port()

    assert choose_port(env.with_port(free)).port == free


# ---------------------------------------------------------------- 二进制可运行


def test_probe_runnable_missing_binary():
    """没装就是不可运行（不抛异常）。"""
    assert probe_runnable(detect(Path("/nonexistent-data"))) == (False, "未安装")


@pytest.mark.skipif(not detect().installed, reason="本机未安装 PostgreSQL 二进制")
def test_probe_runnable_real_binary():
    """真二进制实际执行一次 ``--version``——文件在 ≠ 能跑。"""
    ok, detail = probe_runnable(detect(), fresh=True)

    assert ok is True
    assert "PostgreSQL" in detail


def test_legacy_role_hints_from_pg_authid(tmp_path):
    """老集群的角色名从 pg_authid 数据文件里离线扫出来（换机后猜不到的那个名字）。"""
    from aris.store.pgenv import legacy_role_hints

    pgdata = tmp_path / "pgdata"
    (pgdata / "global").mkdir(parents=True)
    (pgdata / "global" / "1260").write_bytes(
        b"\x00\x01otheradmin\x00pg_monitor\x00pg_read_all_data\x00"
    )

    hints = legacy_role_hints(pgdata)
    assert "otheradmin" in hints
    assert hints.index("otheradmin") < hints.index("pg_monitor")  # 系统角色排最后
    assert legacy_role_hints(tmp_path / "nothing-here") == []


def test_ownership_error_none_for_own_dir(tmp_path):
    """自己的目录没有属主问题。"""
    _init_cluster(tmp_path / "pgdata")

    assert ownership_error(tmp_path / "pgdata") is None
    assert ownership_error(tmp_path / "nothing-here") is None


# ---------------------------------------------------------------- serve 接线


def test_serve_has_data_step(tmp_path, monkeypatch):
    """serve 步骤表里有 data 步骤，且启动动作真的建目录。"""
    from aris.serve.conf import ServeConfig
    from aris.serve.steps import build_steps

    steps = {step.name: step for step in build_steps(ServeConfig())}
    assert "data" in steps

    class _Settings:
        data_dir = tmp_path

    monkeypatch.setattr("aris.serve.steps.get_settings", lambda: _Settings())
    assert "characters" in steps["data"].start()
    assert (tmp_path / "characters").is_dir()
    assert steps["data"].start() == "目录已齐备，无新建"
