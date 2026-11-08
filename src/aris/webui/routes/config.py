"""配置管理路由——查看/编辑 data/config/*.toml；密钥只读展示是否已配置。

**字段清单从文件本身读**，不在本文件维护一份手写表：手写表必然与 dataclass 漂移
（曾经就漏过 `chat.character`）。**写回用 tomlkit 只改对应键**，保留注释与格式。

只处理**扁平键值**的配置文件；`providers.toml` / `mcp.toml` / `modules.toml` /
`settings.toml` 是表结构，各有专用页面或命令，不在这里做通用编辑器。
"""

from __future__ import annotations

import datetime
import os
import shutil
from pathlib import Path
from typing import Any

import tomlkit
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger

from ...infra import paths
from ...infra import toml as cfgtoml
from ..templates import render

router = APIRouter()

# 扁平键值配置文件：name → 页面显示名（结构化文件不在此列）
_FLAT_MODULES: dict[str, str] = {
    "chat": "对话",
    "search": "搜索",
    "audit": "审计",
    "logging": "日志",
    "notify": "通知",
    "webui": "WebUI",
    "store": "存储",
    "knowledge": "知识库",
    "serve": "启动",
}

# 可选的字段说明：只是页面上的小字，缺了不影响功能（因此不会漂移）
_DESCRIPTIONS: dict[str, str] = {
    "chat.temperature": "采样温度，0=确定性，1=随机性较高",
    "chat.top_p": "核采样概率质量",
    "chat.log_rotation_bytes": "对话日志轮转阈值（字节）",
    "chat.tool_result_preview_len": "工具结果预览截断长度",
    "chat.character": "默认角色 cid（留空 = 自动）",
    "search.prefer_engine": "首选搜索引擎（bing/tavily/auto）",
    "search.timeout_seconds": "HTTP 请求超时（秒）",
    "search.results_count": "返回搜索结果条数",
    "search.snippet_max_len": "摘要截断长度（字符）",
    "search.webopen_timeout_seconds": "web_open 超时（秒）",
    "search.webopen_max_chars": "web_open 返回正文最大长度",
    "audit.max_records": "环形缓冲上限",
    "audit.recent_default_limit": "query_recent 默认返回条数",
    "logging.file_rotation": "单个日志文件大小上限",
    "logging.retention": "日志保留期",
    "notify.timeout_seconds": "弹窗子进程超时（秒）",
    "webui.host": "监听地址",
    "webui.port": "监听端口",
    "webui.session_days": "会话有效天数",
}

# 只有标量能在这张通用表单里编辑；表 / 数组留给专用页面
_SCALAR = (str, bool, int, float)


@router.get("/config", response_class=HTMLResponse)
async def config_page(
    request: Request,
    module: str | None = Query(None),
) -> HTMLResponse:
    """配置管理页面。"""
    env_vars = _check_env_vars()
    modules = [{"name": k, "label": v} for k, v in _FLAT_MODULES.items()]
    fields = []
    current_module_label = ""
    if module and module in _FLAT_MODULES:
        fields = _load_module_fields(module)
        current_module_label = _FLAT_MODULES.get(module, module)
    return render(
        request,
        "config.html",
        {
            "active_page": "config",
            "env_vars": env_vars,
            "modules": modules,
            "current_module": module,
            "current_module_label": current_module_label,
            "fields": fields,
        },
    )


@router.post("/config/save", response_model=None)
async def config_save(
    request: Request,
    module: str = Form(...),
) -> RedirectResponse:
    """保存模块配置。module 必须在白名单内（防路径穿越写任意 toml）。"""
    if module not in _FLAT_MODULES:
        return RedirectResponse(url="/config", status_code=303)
    # 备份旧配置
    _backup_config(module)
    # 读取表单数据并写回 toml
    form_data = await request.form()
    _save_module_config(module, dict(form_data))
    return RedirectResponse(url=f"/config?module={module}", status_code=303)


def _check_env_vars() -> list[dict]:
    """检查 ARIS_* 环境变量是否已配置。"""
    vars_to_check = [
        "ARIS_WEBUI_PASSWORD",
        "ARIS_DATA_DIR",
        "ARIS_LLM_PROVIDERS_FILE",
        "TAVILY_API_KEY",
        "OPENCODE_API_KEY",
    ]
    return [{"name": v, "configured": bool(os.environ.get(v))} for v in vars_to_check]


def _user_path(module: str) -> Path:
    """用户配置文件路径（写回目标；不一定存在）。"""
    return cfgtoml.config_dir() / f"{module}.toml"


def _load_doc(module: str) -> tuple[tomlkit.TOMLDocument, Path]:
    """读当前生效的文档：用户文件优先，缺失时用随包种子；返回 (文档, 写回路径)。

    写回路径始终是用户文件——首次保存时把种子内容整体物化过去（注释一并保留）。
    """
    user = _user_path(module)
    source = user if user.is_file() else paths.seed_config_file(f"{module}.toml")
    if source is None:
        return tomlkit.document(), user
    return tomlkit.parse(source.read_text(encoding="utf-8")), user


def _load_module_fields(module: str) -> list[dict]:
    """按文件里的真实键列出可编辑字段（不维护手写清单，避免与代码漂移）。"""
    doc, _ = _load_doc(module)
    fields = []
    for key in doc:
        value = doc[key]
        if not isinstance(value, _SCALAR):
            continue
        fields.append(
            {
                "key": key,
                "value": _display(value),
                "description": _DESCRIPTIONS.get(f"{module}.{key}", ""),
            }
        )
    return fields


def _display(value: Any) -> str:
    """标量 → 输入框文本（bool 统一小写，避免 True/true 两种写法）。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _backup_config(module: str) -> None:
    """备份配置文件到 data/backup/config/。"""
    from ...infra.settings import get_settings

    settings = get_settings()
    src = _user_path(module)
    if not src.exists():
        return
    backup_dir = settings.data_dir / "backup" / "config"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    dst = backup_dir / f"{module}-{ts}.toml"
    shutil.copy2(src, dst)


def _coerce(current: Any, raw: str) -> Any:
    """按**原值的类型**转换表单字符串（不靠猜）。

    猜类型会把字符串 `"123"` 变成整数、把 `"10 MB"` 变成字符串——前者悄悄改语义，
    后者悄悄改类型。类型不符时抛 ValueError，由调用方拒绝该键。
    """
    if isinstance(current, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(current, int):
        return int(raw.strip())
    if isinstance(current, float):
        return float(raw.strip())
    return raw


def _save_module_config(module: str, form_data: dict) -> None:
    """把表单数据写回 toml：只认文件里**已有的键**，其余一律丢弃（防任意键注入）。"""
    doc, user = _load_doc(module)

    for key, raw in form_data.items():
        if key == "module" or key not in doc:
            continue
        current = doc[key]
        if not isinstance(current, _SCALAR):
            continue
        try:
            doc[key] = _coerce(current, str(raw))
        except TypeError, ValueError:
            logger.warning(
                f"配置 {module}.{key} 的值 {raw!r} 与类型 {type(current).__name__} 不符，已忽略"
            )

    user.parent.mkdir(parents=True, exist_ok=True)
    user.write_text(tomlkit.dumps(doc), encoding="utf-8")
