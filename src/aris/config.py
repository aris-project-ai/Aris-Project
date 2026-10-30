"""全局配置（启动级参数与密钥）。

两个来源，都落在 data/config/（路径见 aris.paths），缺失时回落到随包种子模板：

- settings.toml：[settings] 表里的**非密钥**启动参数，键名映射成 ARIS_<KEY> 环境变量
  （例如 log_level → ARIS_LOG_LEVEL）；data_dir 不在这里配，只认进程环境
  ARIS_DATA_DIR（否则鸡生蛋：先要知道 data 在哪才能读配置）。
- secrets.toml：键名**就是**环境变量名（DEEPSEEK_API_KEY 等），只放密钥，
  首次播种时置 0600。

优先级：**进程环境变量 > TOML**。TOML 的值只 setdefault，不覆盖已存在的环境变量；
提供方的 api_key_env 直读 os.environ，靠这一步保持一致。
"""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import paths


def _config_path(name: str) -> Path | None:
    """用户配置优先，缺失时用随包种子模板。"""
    user = paths.config_dir() / name
    if user.is_file():
        return user
    return paths.seed_config_file(name)


def _read_toml(name: str) -> dict:
    path = _config_path(name)
    if path is None:
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        logger.warning(f"配置文件 {path} 读取失败，改用默认值: {exc}")
        return {}
    return data if isinstance(data, dict) else {}


def _load_config_into_environ() -> None:
    """把 TOML 配置注入 os.environ（仅 setdefault，不覆盖进程环境变量）。"""
    settings = _read_toml("settings.toml").get("settings", {})
    if isinstance(settings, dict):
        for key, value in settings.items():
            if not isinstance(key, str) or not key or key == "data_dir":
                continue
            os.environ.setdefault(f"ARIS_{key.upper()}", str(value))
    for key, value in _read_toml("secrets.toml").items():
        if isinstance(key, str) and key and value is not None:
            os.environ.setdefault(key, str(value))


def ensure_config_loaded() -> None:
    """确保 TOML 配置已注入 os.environ（幂等；给直接读 os.environ 的调用方用）。"""
    _load_config_into_environ()


def _default_data_dir() -> Path:
    return paths.data_root()


class Settings(BaseSettings):
    """Aris 全局配置（pydantic-settings，字段带 ARIS_ 前缀）。"""

    model_config = SettingsConfigDict(env_prefix="ARIS_", extra="ignore")

    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=_default_data_dir)

    # LLM 连接
    llm_providers_file: Path = Field(default_factory=lambda: paths.config_dir() / "providers.toml")
    llm_fallback_timeout: float = 30.0
    llm_first_token_stall: float = 3.0  # 首字占位：超过该秒数无产出先显示预设提示语
    llm_error_message: str = "Someone tell Morin there's some problem with my AI."


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例（首次调用时把 TOML 配置 setdefault 进 os.environ）。"""
    _load_config_into_environ()
    return Settings()
