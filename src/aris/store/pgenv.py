"""PostgreSQL 环境探测：定位可用实例并拼装连接参数。

探针链（按序命中即终止，定案见 developDoc/KNOWLEDGE-BASE.md 第 3.1 节）：

1. 环境变量 ``ARIS_PG_BIN``（显式覆盖，指向外部安装的 bin 目录）
2. PATH 中的 ``pg_config``（系统已装则直接用）
3. 项目内 ``data/pg/bin/postgres``（bootstrap 自动装的便携实例）
4. 全无 → 视为未安装，提示先跑 ``aris db init``

可覆盖的环境变量：``ARIS_PG_BIN`` / ``ARIS_PG_PORT`` / ``ARIS_PG_USER`` /
``ARIS_PG_DB`` / ``ARIS_PG_DSN``（整条 DSN 直用，优先级最高）。

**可迁移性（D14，2026-10-01）**：角色名与端口都**不入库、不写配置文件**，只在运行期算，
详见 developDoc/PORTABILITY-AND-SINGLE-SESSION.md：

- **角色名**：新建集群统一用与主机无关的 ``aris``；已有集群读 ``<pgdata>/aris-role``
  标记（标记随 ``pgdata`` 一起搬走），没有标记就先按宿主用户名试（历史行为），
  启动时由 :func:`aris.store.bootstrap.align_user` 在线复核并写回。
- **端口**：默认 ``55432``，被占则启动时换一个可用端口。运行中的实例会把真实端口留在
  unix socket 文件名（``.s.PGSQL.<port>``）里，任何独立进程都能据此反推。
"""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

DEFAULT_PORT = 55432
DEFAULT_DB = "aris"
DEFAULT_USER = "aris"  # 新建集群的超级用户名：与主机用户名无关（D14 缺口②）
PROJECT_DIR_NAME = "pg"  # 便携实例根目录：<data_dir>/pg
PGDATA_NAME = "pgdata"  # 数据目录：<data_dir>/pgdata
ROLE_MARKER_NAME = "aris-role"  # <pgdata>/aris-role：本集群实际角色名（提示，启动时复核）
SOCKET_PREFIX = ".s.PGSQL."  # unix socket 文件名前缀，后接端口号


class PgSource(StrEnum):
    """PostgreSQL 实例来源。"""

    ENV = "env"  # ARIS_PG_BIN 指定
    SYSTEM = "system"  # PATH 中的 pg_config（系统安装）
    PROJECT = "project"  # data/pg（本项目 bootstrap 安装）
    MISSING = "missing"  # 未找到任何可用实例


@dataclass(frozen=True)
class PgEnv:
    """一个 PostgreSQL 实例的运行参数（探测结果 + 本项目约定）。"""

    source: PgSource
    prefix: Path  # 便携实例根目录（<data_dir>/pg）
    bin_dir: Path | None  # 可执行文件目录；未安装时为 None
    pgdata: Path  # 数据目录（<data_dir>/pgdata）
    run_dir: Path  # unix socket 目录（<data_dir>/pg/run）
    log_file: Path  # 服务日志（<data_dir>/pg/postgres.log）
    port: int
    user: str
    dbname: str

    @property
    def installed(self) -> bool:
        """是否已找到可用的 PostgreSQL 可执行文件。"""
        return self.bin_dir is not None

    @property
    def initialized(self) -> bool:
        """数据目录是否已 ``initdb``（与「二进制在不在」是两回事）。"""
        return (self.pgdata / "PG_VERSION").exists()

    @property
    def role_marker(self) -> Path:
        """本集群角色名标记文件（随 ``pgdata`` 一起被搬走）。"""
        return self.pgdata / ROLE_MARKER_NAME

    def with_port(self, port: int) -> PgEnv:
        """换端口（端口只在运行期拼进 DSN，不落任何配置）。"""
        return replace(self, port=port)

    def with_user(self, user: str) -> PgEnv:
        """换角色名（同上，不落配置文件）。"""
        return replace(self, user=user)

    def tool(self, name: str) -> Path:
        """返回实例内某个可执行文件的路径（未安装时报错）。"""
        if self.bin_dir is None:
            raise RuntimeError("PostgreSQL 未安装，请先运行 aris db init")
        return self.bin_dir / name

    @property
    def dsn(self) -> str:
        """连接串：``ARIS_PG_DSN`` 优先，否则按本地 TCP 拼装。"""
        override = os.environ.get("ARIS_PG_DSN")
        if override:
            return override
        return f"postgresql://{self.user}@127.0.0.1:{self.port}/{self.dbname}"

    def tool_env(self) -> dict[str, str]:
        """psql/createdb 等工具的环境变量（走 unix socket，不依赖 TCP 监听）。"""
        return {
            **os.environ,
            "PGHOST": str(self.run_dir),
            "PGPORT": str(self.port),
            "PGUSER": self.user,
            "PGDATABASE": self.dbname,
        }


def _data_dir() -> Path:
    """取全局配置里的数据目录（延迟 import，避免配置层反向依赖本模块）。"""
    from ..config import get_settings

    return Path(get_settings().data_dir)


def _pg_config_bindir(pg_config: str) -> Path | None:
    """由 ``pg_config --bindir`` 得到系统 PostgreSQL 的可执行文件目录。"""
    try:
        out = subprocess.run(
            [pg_config, "--bindir"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    bindir = out.stdout.strip()
    return Path(bindir) if bindir else None


def _probe_bin(prefix: Path) -> tuple[Path | None, PgSource]:
    """按探针链找可执行文件目录，返回 (bin_dir, 来源)。"""
    env_bin = os.environ.get("ARIS_PG_BIN")
    if env_bin and (Path(env_bin) / "postgres").exists():
        return Path(env_bin), PgSource.ENV

    pg_config = shutil.which("pg_config")
    if pg_config:
        bindir = _pg_config_bindir(pg_config)
        if bindir and (bindir / "postgres").exists():
            return bindir, PgSource.SYSTEM

    project_bin = prefix / "bin"
    if (project_bin / "postgres").exists():
        return project_bin, PgSource.PROJECT

    return None, PgSource.MISSING


# 运行期选定的端口（进程内记忆，不落盘）：仅当默认端口被占、本次启动换了端口时才用得上。
# 运行中的实例还会以 unix socket 文件名留下真实端口，供其它进程反推（见 socket_port）。
_runtime_port: int | None = None


def read_role_marker(pgdata: Path) -> str | None:
    """读 ``<pgdata>/aris-role``（不存在或为空返回 None）。"""
    try:
        value = (Path(pgdata) / ROLE_MARKER_NAME).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def write_role_marker(pgdata: Path, user: str) -> Path:
    """写角色名标记（放在 ``pgdata`` 内，随数据目录一起搬走）。"""
    target = Path(pgdata) / ROLE_MARKER_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(f"{user}\n", encoding="utf-8")
    return target


def socket_port(run_dir: Path) -> int | None:
    """从 unix socket 文件名反推运行端口（``.s.PGSQL.<port>``），无则返回 None。

    这是「端口不入库」的落地方式：谁是运行中的实例，谁就留下这个 socket。
    """
    try:
        entries = list(Path(run_dir).iterdir())
    except OSError:
        return None
    for entry in entries:
        name = entry.name
        if name.startswith(SOCKET_PREFIX) and name[len(SOCKET_PREFIX) :].isdigit():
            return int(name[len(SOCKET_PREFIX) :])
    return None


def remember_port(port: int | None) -> None:
    """记住本次运行选定的端口（None = 清空，主要给测试用）。"""
    global _runtime_port
    _runtime_port = port


def port_available(port: int) -> bool:
    """端口是否可在本机绑定（用于判断「被占」）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def free_port() -> int:
    """向内核要一个空闲端口（绑定 0 号端口后读回）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def owner_name(pgdata: Path) -> str | None:
    """数据目录的属主用户名（换机后属主往往变成另一个用户）。"""
    import pwd

    try:
        st = Path(pgdata).stat()
    except OSError:
        return None
    try:
        return pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        return str(st.st_uid)


AUTHID_FILES = ("global/1260", "global/pg_authid")  # pg_authid 的关系文件（版本差异两种名）
_ROLE_TOKEN = re.compile(rb"[A-Za-z_][A-Za-z0-9_$]{0,62}")


def legacy_role_hints(pgdata: Path) -> list[str]:
    """从 ``pg_authid`` 数据文件里**离线**捞出候选角色名（换机后角色名猜不到时用）。

    换机（D14 缺口②）最麻烦的情形是：老集群的角色名 = **老主机**的用户名，与本机
    ``$USER`` 毫不相干，又没有标记文件时无处可猜。``pg_authid`` 里角色名是裸明文，
    扫出来当**候选**即可——真正的判定仍以在线实连为准，猜错只是多一次失败尝试。

    只读文件、不改动任何东西；文件不存在（版本差异）时返回空列表。
    系统角色（``pg_*``）几乎不可能是 initdb 时用的名字，排在最后。
    """
    names: list[str] = []
    for rel in AUTHID_FILES:
        try:
            data = (Path(pgdata) / rel).read_bytes()
        except OSError:
            continue
        for token in _ROLE_TOKEN.findall(data):
            name = token.decode("ascii", "ignore")
            if name and name not in names:
                names.append(name)
    names.sort(key=lambda n: n.startswith("pg_"))
    return names


def ownership_error(pgdata: Path) -> str | None:
    """数据目录属主与当前用户不一致时给出**可操作提示**（不自动修，D14 缺口②）。

    PostgreSQL 拒绝以非属主身份启动，而 chown 是用户自己的决定（可能要 sudo），
    故这里只报错并把命令写清楚。
    """
    import pwd

    try:
        st = Path(pgdata).stat()
    except OSError:
        return None
    if st.st_uid == os.geteuid():
        return None
    owner = owner_name(pgdata) or str(st.st_uid)
    try:
        me = pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        me = str(os.geteuid())
    return (
        f"数据目录属主是 {owner}，当前用户是 {me}——PostgreSQL 不会以非属主身份启动。"
        f"处理：sudo chown -R {me} {pgdata}（或删掉 {pgdata} 重建，代价是丢记忆）"
    )


def _resolve_port(prefix: Path) -> int:
    """端口优先级：``ARIS_PG_PORT`` > 运行中实例的 socket > 本次运行选定 > 默认。"""
    explicit = os.environ.get("ARIS_PG_PORT")
    if explicit:
        try:
            return int(explicit)
        except ValueError:
            pass
    running = socket_port(prefix / "run")
    if running is not None:
        return running
    return _runtime_port if _runtime_port is not None else DEFAULT_PORT


def _resolve_user(pgdata: Path) -> str:
    """角色名优先级：``ARIS_PG_USER`` > 标记文件 > 老集群按宿主用户名 > 新建集群用 aris。"""
    explicit = os.environ.get("ARIS_PG_USER")
    if explicit:
        return explicit
    marker = read_role_marker(pgdata)
    if marker:
        return marker
    if (Path(pgdata) / "PG_VERSION").exists():
        # 老集群（当时用 initdb -U $USER 建的）：先按宿主用户名试，
        # 启动时 align_user 会在线复核并写标记。
        return os.environ.get("USER") or "postgres"
    return DEFAULT_USER


def detect(data_dir: Path | str | None = None) -> PgEnv:
    """执行探针链，返回当前应使用的 PostgreSQL 环境。

    路径一律转成**绝对路径**：PostgreSQL 启动后会 chdir 到数据目录，``-k``/``-D``
    传相对路径会被解析到错误位置。
    """
    root = Path(data_dir) if data_dir is not None else _data_dir()
    if not root.is_absolute():
        root = Path.cwd() / root
    root = root.resolve()
    prefix = root / PROJECT_DIR_NAME
    bin_dir, source = _probe_bin(prefix)
    pgdata = root / PGDATA_NAME
    return PgEnv(
        source=source,
        prefix=prefix,
        bin_dir=bin_dir,
        pgdata=pgdata,
        run_dir=prefix / "run",
        log_file=prefix / "postgres.log",
        port=_resolve_port(prefix),
        user=_resolve_user(pgdata),
        dbname=os.environ.get("ARIS_PG_DB", DEFAULT_DB),
    )


__all__ = [
    "DEFAULT_DB",
    "DEFAULT_PORT",
    "DEFAULT_USER",
    "PGDATA_NAME",
    "ROLE_MARKER_NAME",
    "PgEnv",
    "PgSource",
    "detect",
    "free_port",
    "owner_name",
    "ownership_error",
    "port_available",
    "read_role_marker",
    "remember_port",
    "socket_port",
    "write_role_marker",
]
