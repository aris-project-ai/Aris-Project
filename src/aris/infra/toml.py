"""模块级配置文件加载：data/config/*.toml。

各功能模块的可调参数（超时、轮数、日志轮转等）收口到模块级 toml，优先级：
**代码内 dataclass 默认值 < data/config/<name>.toml**。用户文件缺失时退回随包
种子模板（src/aris/seed/config/）读默认值；缺键一律用代码默认。

边界：启动级参数与密钥见 aris.infra.settings（settings.toml / secrets.toml）；本模块只管
模块可调参数。配置目录由 aris.infra.paths.config_dir() 决定，与运行 cwd 无关。
"""

from __future__ import annotations

import tomllib
from dataclasses import fields, is_dataclass
from pathlib import Path

from loguru import logger

from . import paths


def config_dir() -> Path:
    """配置目录（= aris.infra.paths.config_dir()，历史调用点保留这个入口）。"""
    return paths.config_dir()


def config_path(filename: str) -> Path | None:
    """配置文件路径：用户配置优先，缺失时退回随包种子模板（都没有则 None）。"""
    user = paths.config_dir() / filename
    if user.is_file():
        return user
    return paths.seed_config_file(filename)


def load_config[T](instance: T, filename: str) -> T:
    """把配置文件里与 dataclass 字段同名的键覆盖到实例。

    文件缺失、解析失败或键不存在时静默用默认值，不抛异常
    （配置缺失不致命，代码内默认值兜底）。
    """
    path = config_path(filename)
    if path is None:
        return instance
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        logger.warning(f"配置文件 {path} 解析失败，使用默认值: {e}")
        return instance
    except OSError as e:
        logger.warning(f"配置文件 {path} 读取失败，使用默认值: {e}")
        return instance
    if not is_dataclass(instance):
        raise TypeError(f"load_config 需要 dataclass 实例，得到 {type(instance)!r}")
    for field in fields(instance):
        if field.name in data:
            setattr(instance, field.name, data[field.name])
    return instance
