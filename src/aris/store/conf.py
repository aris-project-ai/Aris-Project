"""store 模块的可调参数（优先级：代码内默认值 < `data/config/store.toml`）。

遵循配置体系收口原则（见 docs/forAiDoc/CONFIG.md）：只放**真正可调**的参数，
provider 之类的逻辑类型留在代码里；密钥一律走 data/config/secrets.toml。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from ..infra.components import BEKKO_A25M
from ..infra.toml import load_config


@dataclass
class StoreConfig:
    """store 模块配置。"""

    # embedding 提供方（当前支持 "local" = 本地 Bekko a25m，384 维）
    embedding_provider: str = "local"
    # 本地模型：HF 仓库 id，或 data/models/ 下的目录名；默认值来自 infra/components.py
    local_model: str = BEKKO_A25M.repo
    # 本地推理一次喂多少条
    batch_size: int = 16
    # Matryoshka 截断维度（None = 用模型原生维度 384）
    truncate_dim: int | None = None
    # 外部组件镜像（只换下载地址，sha256 仍取 infra/components.py）：
    # "<id>" = 镜像目录（自动拼官方文件名）；"<id>.<platform>" = 完整 URL 精确覆盖
    mirror: dict[str, str] = field(default_factory=dict)


@lru_cache
def get_store_config() -> StoreConfig:
    """加载 store 配置单例。"""
    return load_config(StoreConfig(), "store.toml")
