"""便携 PostgreSQL + pgvector 的获取与初始化（幂等）。

不要求用户预装系统 PostgreSQL（定案见 docs/forAiDoc/KNOWLEDGE-BASE.md 第 3 节）：
缺什么补什么——下载 micromamba（含 sha256 校验）→ 在 ``data/pg`` 建 conda 环境
（``postgresql`` 与 ``pgvector`` 同源，版本匹配由 solver 保证）→ ``initdb`` →
启动 → 建库 → 建 ``vector`` 扩展。全部产物落在 ``data/`` 下（gitignore 已覆盖），
仓库零体积增长；代码只认连接串，不感知实例来源。

**可迁移性（D14，2026-10-01）**本模块负责三件事：

- :func:`probe_runnable` —— 二进制**实际能跑**才算可用（换平台后文件在 ≠ 能跑），
  不可用且来源是 ``data/pg`` 时 :func:`bootstrap_env` 会**重新获取**（``force=True``）；
- :func:`choose_port` —— 端口被占时换一个可用端口（端口不落任何配置）；
- :func:`align_user` —— 角色名在线复核并写回 ``<pgdata>/aris-role``（换机后角色名不同）。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

from loguru import logger

from .pgenv import (
    SOCKET_PREFIX,
    PgEnv,
    PgSource,
    detect,
    free_port,
    legacy_role_hints,
    owner_name,
    port_available,
    remember_port,
    write_role_marker,
)

# micromamba 固定版本 + 官方 sha256（升级时两处一起人工更新）
MAMBA_VERSION = "2.9.0-0"
MAMBA_URL = (
    "https://github.com/mamba-org/micromamba-releases/releases/download/"
    f"{MAMBA_VERSION}/micromamba-linux-64"
)
MAMBA_SHA256 = "366cd9cd8be14df1ab8ed50352a82111082a36686b2d389fdb79a92c3fafb3e3"

PG_VERSION = "17"
PGVECTOR_SPEC = "pgvector>=0.8"
CONDA_CHANNEL = "conda-forge"

DOWNLOAD_TIMEOUT = 600  # 秒；conda 环境首次下载可能较慢
CHUNK_SIZE = 1 << 20


class BootstrapError(RuntimeError):
    """bootstrap 过程中的可读错误（下载失败 / 命令失败 / 校验失败）。"""


def _sha256(path: Path) -> str:
    """计算文件 sha256（分块读取，避免整包进内存）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> str:
    """执行外部命令；失败抛 :class:`BootstrapError`（带 stderr 末尾几行）。"""
    logger.debug(f"执行: {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or "").strip().splitlines()
        tail = " / ".join(lines[-3:]) if lines else f"退出码 {proc.returncode}"
        raise BootstrapError(f"{Path(cmd[0]).name} 执行失败：{tail}")
    return proc.stdout


def mamba_path(env: PgEnv) -> Path:
    """micromamba 的落地位置（放在便携实例的同级 bin 目录，避开环境自身）。"""
    return env.prefix.parent / "bin" / "micromamba"


def ensure_micromamba(env: PgEnv) -> Path:
    """确保 micromamba 就位：已存在且 sha256 匹配则复用，否则下载校验。"""
    dest = mamba_path(env)
    if dest.exists() and _sha256(dest) == MAMBA_SHA256:
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    logger.info(f"下载 micromamba {MAMBA_VERSION} ...")
    try:
        with (
            urllib.request.urlopen(MAMBA_URL, timeout=DOWNLOAD_TIMEOUT) as resp,
            open(tmp, "wb") as fh,
        ):
            shutil.copyfileobj(resp, fh)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise BootstrapError(f"下载 micromamba 失败：{exc}") from exc

    digest = _sha256(tmp)
    if digest != MAMBA_SHA256:
        tmp.unlink(missing_ok=True)
        raise BootstrapError(f"micromamba sha256 不匹配：期望 {MAMBA_SHA256}，实际 {digest}")
    tmp.chmod(0o755)
    tmp.replace(dest)
    logger.success(f"micromamba 就位：{dest}")
    return dest


def ensure_pg_env(env: PgEnv, mamba: Path) -> None:
    """确保 conda 环境内已装 postgresql + pgvector（已装则跳过）。"""
    if (env.prefix / "bin" / "postgres").exists():
        return
    logger.info(f"安装 PostgreSQL {PG_VERSION} + pgvector 到 {env.prefix}（首次约 40MB）...")
    # 根前缀、包缓存、libmamba 元数据缓存全部收在 data/ 下：
    # 不污染用户主目录，清理时随 data/ 一起走。
    # micromamba 仍会写 ~/.conda/environments.txt 与 ~/.mambarc，故把 HOME 也指到 data/。
    root = env.prefix.parent
    mamba_env = {
        **env.tool_env(),
        "MAMBA_ROOT_PREFIX": str(root / "pg-root"),
        "CONDA_PKGS_DIRS": str(root / "pg-pkgs"),
        "XDG_CACHE_HOME": str(root / ".cache"),
        "HOME": str(root / ".home"),
    }
    _run(
        [
            str(mamba),
            "create",
            "-y",
            "-p",
            str(env.prefix),
            "-c",
            CONDA_CHANNEL,
            f"postgresql={PG_VERSION}",
            PGVECTOR_SPEC,
        ],
        env=mamba_env,
    )


def ensure_cluster(env: PgEnv) -> None:
    """``initdb`` 初始化数据目录（已初始化则跳过）。

    新建的集群统一用 :data:`aris.store.pgenv.DEFAULT_USER`（``aris``）做超级用户，
    **与主机用户名无关**——这正是 D14 缺口②的解法：换机后 ``pgdata`` 拷过来即可用。
    """
    if (env.pgdata / "PG_VERSION").exists():
        return
    env.pgdata.mkdir(parents=True, exist_ok=True)
    env.run_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"初始化数据目录 {env.pgdata}（角色 {env.user}）...")
    _run(
        [
            str(env.tool("initdb")),
            "-D",
            str(env.pgdata),
            "-U",
            env.user,
            "--encoding=UTF8",
            "--no-locale",  # 避免依赖宿主 locale；排序用 C
            "--auth-local=trust",
            "--auth-host=trust",
        ]
    )
    logger.success("数据目录初始化完成")


# 「二进制能不能跑」的进程内缓存：detect() 调用很频繁，不值得每次 fork 一个进程
_runnable_cache: dict[str, tuple[bool, str]] = {}


def probe_runnable(env: PgEnv, *, fresh: bool = False) -> tuple[bool, str]:
    """验证 PG 二进制**实际可运行**（不只是文件存在）。

    D14 缺口①：``data/pg`` 里的可执行文件是平台相关的（Linux x86_64 ≠ macOS ≠
    aarch64），换机拷过来后文件还在但一跑就报"格式错误/无法执行"。所以这里真的执行
    一次 ``postgres --version``，而不是查 ``.exists()``。结果进程内缓存。
    """
    if not env.installed or env.bin_dir is None:
        return False, "未安装"
    key = str(env.bin_dir)
    if not fresh and key in _runnable_cache:
        return _runnable_cache[key]
    postgres = env.bin_dir / "postgres"
    try:
        proc = subprocess.run(
            [str(postgres), "--version"], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError) as exc:
        result = (False, f"无法执行 {postgres}：{exc}")
    else:
        if proc.returncode == 0:
            result = (True, (proc.stdout or proc.stderr).strip() or "ok")
        else:
            lines = (proc.stderr or proc.stdout or "").strip().splitlines()
            result = (False, lines[-1] if lines else f"退出码 {proc.returncode}")
    _runnable_cache[key] = result
    return result


def choose_port(env: PgEnv) -> PgEnv:
    """端口被占时换一个可用端口（只在「准备启动」时调用）。

    D14 缺口③：默认端口 ``55432`` 可能被别的进程占着。端口**不写任何配置文件**——
    只记在进程内 + 由运行中实例的 unix socket 文件名对外可见，故 ``aris db psql``
    这类独立进程也能找对端口。
    """
    if port_available(env.port):
        remember_port(env.port)
        return env
    port = free_port()
    logger.warning(f"端口 {env.port} 已被占用，本次改用 {port}（不写入配置，重启会重新探测）")
    remember_port(port)
    return env.with_port(port)


def _role_connects(env: PgEnv, user: str) -> bool:
    """以某个角色连一次库（``trust`` 认证下角色不存在会直接失败）。"""
    try:
        proc = subprocess.run(
            [
                str(env.tool("psql")),
                "-h",
                str(env.run_dir),
                "-p",
                str(env.port),
                "-U",
                user,
                "-d",
                "postgres",
                "-tAc",
                "SELECT 1",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "1"


def align_user(env: PgEnv) -> PgEnv:
    """在线确认本集群真正可用的角色名，并把结果写回 ``<pgdata>/aris-role``。

    换机后 ``pgdata`` 拷过来、宿主用户名却变了（D14 缺口②）：老集群的角色名仍是
    initdb 时写下的那个，凭 ``$USER`` 猜不到。这里按候选顺序实连一次，命中即写标记
    （标记随 ``pgdata`` 一起搬走，下次直接命中，不必再探测）。候选除本机用户名外，
    还包括 :func:`aris.store.pgenv.legacy_role_hints` 从 ``pg_authid`` 里扫出来的名字。

    ``ARIS_PG_USER`` 显式指定时以用户为准，不探测。
    """
    if os.environ.get("ARIS_PG_USER"):
        return env
    candidates = [env.user, "aris"]
    candidates += legacy_role_hints(env.pgdata)
    candidates += [os.environ.get("USER") or "", owner_name(env.pgdata) or "", "postgres"]
    seen: list[str] = []
    for name in candidates:
        if name and name not in seen:
            seen.append(name)
    for name in seen:
        if _role_connects(env, name):
            if name != env.user:
                logger.info(f"角色探测对齐：本集群的角色是 {name}（探测前按 {env.user} 猜的）")
            write_role_marker(env.pgdata, name)
            return env.with_user(name)
    raise BootstrapError(
        f"连不上本集群：候选角色（{', '.join(seen)}）在端口 {env.port} 上都不通——"
        "用 ARIS_PG_USER 指定本实例的角色名，或删掉 data/pgdata 重建（会丢记忆）"
    )


def is_running(env: PgEnv) -> bool:
    """实例是否正在运行（未安装或未初始化一律视为未运行）。

    只看 ``pg_ctl status`` 不够：崩溃后残留的 ``postmaster.pid``（PID 被复用、
    或换了 PID 命名空间）会让它报"在运行"。故再用 ``pg_isready`` 真实探一次。

    退出码语义：``0`` 接受连接、``1`` 服务器在线但拒绝本次探测（例如默认库不存在、
    或正在启动中）、``2`` 无响应、``3`` 参数不合法——**只有 0/1 算在跑**，
    否则启动流程会在"库还没建好"时误判成没起、重复去启一个已经起来的实例。
    """
    if not env.installed or not (env.pgdata / "PG_VERSION").exists():
        return False
    proc = subprocess.run(
        [str(env.tool("pg_ctl")), "-D", str(env.pgdata), "status"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return False
    ready = subprocess.run(
        [str(env.tool("pg_isready")), "-h", str(env.run_dir), "-p", str(env.port)],
        capture_output=True,
        text=True,
    )
    return ready.returncode in (0, 1)


def _clear_stale_runtime(env: PgEnv) -> bool:
    """清理「服务已不在、残留文件还在」的现场（崩溃 / 换主机后常见）。

    要清两类：

    - ``postmaster.pid``：``pg_ctl`` 靠它判断"是否已有 postmaster"，PID 被复用必然误判，
      直接拒绝启动；
    - run 目录里的 ``.s.PGSQL.*``（含 ``.lock``）：postgres 只在正常关闭时删它们，
      崩溃后残留会让下一次启动报 ``lock file already exists`` 而**直接起不来**
      （实测踩过：清掉 pidfile 还不够）。

    返回是否真的清了东西。
    """
    cleaned = False
    pid_file = env.pgdata / "postmaster.pid"
    if pid_file.exists():
        logger.warning(f"发现残留 {pid_file.name}（服务实际无响应），清理后继续")
        pid_file.unlink(missing_ok=True)
        cleaned = True
    if env.run_dir.exists():
        stale = [p for p in env.run_dir.iterdir() if p.name.startswith(SOCKET_PREFIX)]
        if stale:
            logger.warning(f"发现残留 socket 文件 {len(stale)} 个（服务实际无响应），清理后继续")
            for path in stale:
                path.unlink(missing_ok=True)
            cleaned = True
    return cleaned


def _log_tail(env: PgEnv, lines: int = 5) -> str:
    """读服务日志末尾若干行，用于启动失败时的诊断。"""
    if not env.log_file.exists():
        return ""
    tail = env.log_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    return " / ".join(tail[-lines:])


def start(env: PgEnv) -> bool:
    """启动服务；已在运行则返回 False（无操作）。"""
    if is_running(env):
        return False
    _clear_stale_runtime(env)
    env.run_dir.mkdir(parents=True, exist_ok=True)
    env.log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run(
            [
                str(env.tool("pg_ctl")),
                "-D",
                str(env.pgdata),
                "-l",
                str(env.log_file),
                "-o",
                f"-p {env.port} -k {env.run_dir} -h 127.0.0.1",
                "-w",
                "-t",
                "60",
                "start",
            ]
        )
    except BootstrapError as exc:
        # pg_ctl 自身信息很少，把服务日志末尾一起抛出便于定位
        tail = _log_tail(env)
        hint = ""
        if "pre-existing shared memory block" in tail or "another server might" in tail:
            hint = (
                "；检测到上次异常退出遗留的 postgres 进程仍占用共享内存"
                f"（该实例仅属本项目，结束它即可）：pkill -f {env.pgdata}"
            )
        raise BootstrapError(f"{exc}；服务日志：{tail}{hint}") from exc
    return True


def stop(env: PgEnv) -> bool:
    """停止服务；本就未运行则返回 False（无操作，顺手清残留 pidfile）。"""
    if not is_running(env):
        _clear_stale_runtime(env)
        return False
    _run([str(env.tool("pg_ctl")), "-D", str(env.pgdata), "-m", "fast", "-w", "stop"])
    return True


def ensure_database(env: PgEnv) -> None:
    """建库 + 建 ``vector`` 扩展（幂等）。"""
    psql = str(env.tool("psql"))
    tool_env = env.tool_env()
    probe_env = {**tool_env, "PGDATABASE": "postgres"}  # 目标库可能尚不存在
    exists = _run(
        [psql, "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{env.dbname}'"],
        env=probe_env,
    ).strip()
    if not exists:
        logger.info(f"创建数据库 {env.dbname} ...")
        _run([str(env.tool("createdb")), env.dbname], env=tool_env)
    _run(
        [psql, "-d", env.dbname, "-c", "CREATE EXTENSION IF NOT EXISTS vector"],
        env=tool_env,
    )


def write_versions(env: PgEnv) -> Path:
    """把当前实例版本写入 ``<prefix>/versions.txt``，便于日后排查。"""
    psql = str(env.tool("psql"))
    tool_env = env.tool_env()
    server = _run([psql, "-tAc", "SHOW server_version"], env=tool_env).strip()
    vector = _run(
        [
            psql,
            "-tAc",
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'",
        ],
        env=tool_env,
    ).strip()
    target = env.prefix / "versions.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"postgresql={server}\npgvector={vector or 'missing'}\n"
        f"provider={env.source}\nport={env.port}\nrole={env.user}\ndb={env.dbname}\n",
        encoding="utf-8",
    )
    return target


def bootstrap_env(env: PgEnv, *, force: bool = False) -> PgEnv:
    """一条龙：探测 → 装 micromamba → 装 PG + pgvector → initdb → 启动 → 建库。

    系统已装（``ARIS_PG_BIN`` / ``pg_config``）时**不下载**，只确保库与扩展存在。
    返回可能已刷新的 :class:`PgEnv`（刚装完便携实例时来源与 bin 目录会变）。

    ``force=True``（D14 缺口①）：``data/pg`` 里的二进制在本机跑不起来（换了平台 /
    架构）时，删掉这个**可重建**目录重新获取；``data/pgdata``（记忆全在这）绝不动。

    命名带 ``_env`` 后缀是刻意的：函数若与模块同名（``bootstrap``），
    包内 ``from .bootstrap import bootstrap`` 会把它遮蔽成模块属性，
    调用方 ``store.bootstrap`` 拿到的就不是模块了（已踩过）。
    """
    if force and env.source is PgSource.PROJECT:
        logger.warning(
            f"重新获取便携 PostgreSQL（删除可重建的 {env.prefix}；数据目录 {env.pgdata} 保持不动）"
        )
        shutil.rmtree(env.prefix, ignore_errors=True)
        _runnable_cache.clear()
        env = detect(env.prefix.parent)

    if env.source in (PgSource.ENV, PgSource.SYSTEM):
        ok, why = probe_runnable(env, fresh=True)
        if not ok:
            raise BootstrapError(f"指定的 PostgreSQL 无法运行：{why}")
        logger.info(f"使用已有 PostgreSQL 实例（{env.bin_dir}），跳过下载")
    else:
        mamba = ensure_micromamba(env)
        ensure_pg_env(env, mamba)
        env = detect(env.prefix.parent)  # 装好后 bin_dir 才存在，重新探测

    ensure_cluster(env)
    env = choose_port(env)
    if start(env):
        logger.success(f"数据库已启动（端口 {env.port}）")
    else:
        logger.info(f"数据库已在运行（端口 {env.port}）")
    env = align_user(env)
    ensure_database(env)
    versions = write_versions(env)
    logger.success(f"数据库就绪：{env.dsn}")
    logger.info(f"版本清单：{versions}")
    return env
