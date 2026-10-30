"""knowledge 模块的可调参数（优先级：代码内默认值 < `data/config/knowledge.toml`）。

只放**真正可调**的参数（分块尺寸、检索条数、索引参数）；模块开关不在这里，
统一由 `data/config/modules.toml` 管（v0.4.4 W3 起）。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..infra.toml import load_config


@dataclass
class KnowledgeConfig:
    """知识库可调参数。"""

    # 单块字符上限（超过则按段落/句子做定长兜底切分）
    max_chars: int = 800
    # 单块字符下限（打包段落时至少凑到这个长度，避免碎片块）
    min_chars: int = 120
    # 定长兜底切分时的重叠比例（0.15 = 15%）
    overlap_ratio: float = 0.15
    # 检索默认返回条数
    top_k: int = 5
    # HNSW 查询期 ef_search
    ef_search: int = 40
    # HNSW 建索引参数（先用 pgvector 默认值，数据量上来再调）
    index_m: int = 16
    index_ef_construction: int = 64
    # 上传（WebUI）落盘目录：空 = <data_dir>/knowledge；上传文件同名覆盖
    upload_dir: str = ""
    # 单文件体积上限（字节）与单次上传文件数上限
    max_file_bytes: int = 10 * 1024 * 1024
    max_files_per_upload: int = 50


@lru_cache
def get_knowledge_config() -> KnowledgeConfig:
    """加载知识库配置单例。"""
    return load_config(KnowledgeConfig(), "knowledge.toml")
