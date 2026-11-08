"""外部组件清单：运行期要下载 / 安装到 ``data/`` 的第三方产物，一处给出版本与校验值。

定位（2026-11-06 定，见 `docs/process/v1.0.0-prep.md` §3.8）：

- **代码事实，不是配置**：不进设置页、不随配置档；升级 = 改这里 + 发版。
- **只收运行期真的要获取的东西**：便携 PostgreSQL、pgvector、micromamba、embedding 模型。
  uv 是打包时的构建工具（deb 里随包分发），运行期一次都不用，故**不收**——它归 S13 打包脚本。
- **缺校验即失败**：可下载条目的 ``sha256`` 缺失或对不上时抛 :class:`ComponentsError`，
  不允许「跳过校验继续装」。
- **用户只能换下载地址**：镜像覆盖读 ``data/config/store.toml`` 的 ``[mirror]``，
  只替换 URL，``sha256`` 永远取本模块；镜像必须是字节一致的副本。

本模块**不 import 业务模块**（``infra`` 的边界），因此不自己读配置：镜像表由调用方传入。
"""

from __future__ import annotations

import platform as _platform
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

# 当前只承诺 Linux 两个架构；其它平台明确报错，不做猜测映射
type Platform = Literal["linux-64", "linux-aarch64"]

SUPPORTED_PLATFORMS: tuple[Platform, ...] = ("linux-64", "linux-aarch64")


class ComponentsError(RuntimeError):
    """外部组件清单相关错误（平台不支持 / 缺校验 / 条目不存在 / 镜像非法）。"""


def platform_key() -> Platform:
    """``sys.platform`` + CPU 架构归一成本清单使用的平台键。

    只认 Linux；``libc`` 差异（glibc / musl）不在这里区分——当前不发布 musl 产物。
    """
    if sys.platform != "linux":
        raise ComponentsError(f"暂不支持的平台：{sys.platform}（当前只支持 Linux）")
    machine = _platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "linux-64"
    if machine in {"aarch64", "arm64"}:
        return "linux-aarch64"
    raise ComponentsError(f"暂不支持的 CPU 架构：{machine}（当前只支持 x86_64 / aarch64）")


@dataclass(frozen=True, slots=True)
class Archive:
    """直接下载的单个文件；每个受支持平台都必须给出文件名与 sha256。"""

    id: str
    version: str
    base_url: str  # 官方下载前缀，最终 URL = base_url + "/" + files[platform]
    files: Mapping[Platform, str]  # 平台 → 官方文件名（镜像目录同样按这个拼）
    sha256: Mapping[Platform, str]

    def url(self, platform: Platform) -> str:
        """某平台的官方下载地址。"""
        filename = self.files.get(platform, "").strip()
        if not filename:
            raise ComponentsError(f"组件 {self.id} 没有 {platform} 的产物")
        return f"{self.base_url.rstrip('/')}/{filename}"


@dataclass(frozen=True, slots=True)
class CondaPackage:
    """交给 conda 求解的包：精确版本，完整性由 conda 的 repodata 负责。"""

    id: str
    version: str
    channel: str


@dataclass(frozen=True, slots=True)
class Model:
    """Hugging Face 模型：用 commit 锁死，不跟 ``main`` 或 tag。"""

    id: str
    repo: str
    revision: str
    dimension: int
    license: str


type Component = Archive | CondaPackage | Model


# ---------------------------------------------------------------------------
# 清单本体
#
# PostgreSQL / pgvector 版本绑死：pgvector 0.8.6 要求 libpq >= 18.6，
# 而 PG 17 最高只能配 0.8.1。S5 会把这一对升到 18.6 / 0.8.6 并重建 data/pgdata，
# 在那之前保持 17 / 0.8.1（与现有开发库一致，避免无谓重建）。
# ---------------------------------------------------------------------------

POSTGRESQL = CondaPackage(id="postgresql", version="17", channel="conda-forge")
PGVECTOR = CondaPackage(id="pgvector", version="0.8.1", channel="conda-forge")

_MICROMAMBA_VERSION = "2.9.0-0"
_MICROMAMBA_BASE = (
    f"https://github.com/mamba-org/micromamba-releases/releases/download/{_MICROMAMBA_VERSION}"
)

MICROMAMBA = Archive(
    id="micromamba",
    version=_MICROMAMBA_VERSION,
    base_url=_MICROMAMBA_BASE,
    files={p: f"micromamba-{p}" for p in SUPPORTED_PLATFORMS},
    sha256={
        "linux-64": "366cd9cd8be14df1ab8ed50352a82111082a36686b2d389fdb79a92c3fafb3e3",
        "linux-aarch64": "9f93b974adcb4d166996af969b6cd371287d1a3e52733704727884d9b74cb7a7",
    },
)

BEKKO_A25M = Model(
    id="bekko-a25m",
    repo="hotchpotch/bekko-embedding-v1-a25m",
    revision="44f0b8af0f487acd0ccf1a7cb7ae7a29a6dfc09c",
    dimension=384,
    license="MIT",
)

COMPONENTS: tuple[Component, ...] = (MICROMAMBA, POSTGRESQL, PGVECTOR, BEKKO_A25M)


# ---------------------------------------------------------------------------
# 取用
# ---------------------------------------------------------------------------


def all_components() -> tuple[Component, ...]:
    """清单全量（按声明顺序；CLI 与测试用）。"""
    return COMPONENTS


def by_id(component_id: str) -> Component:
    """按 ``id`` 取条目；不存在时报错并列出可用 id。"""
    for component in COMPONENTS:
        if component.id == component_id:
            return component
    known = ", ".join(c.id for c in COMPONENTS)
    raise ComponentsError(f"未知的外部组件：{component_id}（可用：{known}）")


def require_sha(component: Archive, platform: Platform | None = None) -> str:
    """取某平台的 sha256；缺失 / 空串 / 非 64 位十六进制都直接报错。"""
    key = platform or platform_key()
    digest = component.sha256.get(key, "").strip().lower()
    if not digest:
        raise ComponentsError(
            f"组件 {component.id} 缺少 {key} 的 sha256——缺校验不允许安装，请先在清单里补上"
        )
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ComponentsError(f"组件 {component.id} 的 {key} sha256 格式非法：{digest!r}")
    return digest


def resolve_url(
    component: Archive,
    platform: Platform | None = None,
    mirrors: Mapping[str, str] | None = None,
) -> str:
    """取下载地址：先查镜像覆盖，再回落到官方地址。

    镜像键（``data/config/store.toml`` 的 ``[mirror]``）：
    - ``"<id>"``：**镜像目录**，按当前平台自动拼上官方文件名
      （``micromamba = "https://mirror.example/releases/2.9.0-0"`` →
      ``.../2.9.0-0/micromamba-linux-64``）；
    - ``"<id>.<platform>"``：**完整 URL**，单平台精确覆盖，优先级最高。

    镜像只换地址，``sha256`` 仍取 :func:`require_sha`——镜像必须字节一致。
    """
    key = platform or platform_key()
    default = component.url(key)
    if not mirrors:
        return default

    exact_key = f"{component.id}.{key}"
    exact = mirrors.get(exact_key)
    if exact is not None:
        if not isinstance(exact, str) or not exact.strip():
            raise ComponentsError(f"镜像 {exact_key} 必须是非空 URL 字符串")
        return exact.strip()

    base = mirrors.get(component.id)
    if base is None:
        return default
    if not isinstance(base, str) or not base.strip():
        raise ComponentsError(f"镜像 {component.id} 必须是非空 URL 字符串")
    return f"{base.strip().rstrip('/')}/{component.files[key]}"


def as_dict(component: Component) -> dict[str, object]:
    """给 CLI ``--json`` 与前端用的 JSON 安全视图。"""
    if isinstance(component, Archive):
        return {
            "id": component.id,
            "kind": "archive",
            "version": component.version,
            "urls": {p: component.url(p) for p in component.files},
            "sha256": dict(component.sha256),
        }
    if isinstance(component, CondaPackage):
        return {
            "id": component.id,
            "kind": "conda",
            "version": component.version,
            "channel": component.channel,
        }
    return {
        "id": component.id,
        "kind": "model",
        "repo": component.repo,
        "revision": component.revision,
        "dimension": component.dimension,
        "license": component.license,
    }


__all__ = [
    "BEKKO_A25M",
    "COMPONENTS",
    "MICROMAMBA",
    "PGVECTOR",
    "POSTGRESQL",
    "SUPPORTED_PLATFORMS",
    "Archive",
    "Component",
    "ComponentsError",
    "CondaPackage",
    "Model",
    "Platform",
    "all_components",
    "as_dict",
    "by_id",
    "platform_key",
    "require_sha",
    "resolve_url",
]
