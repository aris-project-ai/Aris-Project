"""/models 同步核心逻辑：拉取 + 对比 + models.dev enrichment + 写回 + 缺失记录。

设计见 `docs/forAiDoc/LLM-PROVIDER-MGMT.md` 阶段二。本模块保持纯逻辑
（不依赖 prompt_toolkit），交互勾选 UI 在 cli.py 组装。

同步规则（白名单语义）：
- 云有本地无 → 添加候选（默认不自动加，由用户勾选；非 TTY --write 全加）
- 两边都有 → 保留
- 本地有云无 → 从配置移除，并写入 `data/state/llm-list-missing.json`
  （只读留档：无宽限期、无自动恢复）
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx
import tomli_w
from loguru import logger

from aris import paths

from .config import LLMModel, LLMProvider, ProviderConfig, load_providers
from .errors import AuthError, LLMError
from .message import ApiFormat

MISSING_FILE_NAME = "llm-list-missing.json"

# models.dev 数据源与缓存策略
MODELSDEV_URL = "https://models.dev/api.json"
MODELSDEV_CACHE_TTL = 7 * 24 * 3600  # 秒


# ---------- 拉取 /models ----------


def fetch_provider_models(provider: LLMProvider, timeout: float = 20.0) -> list[str]:
    """GET {base_url}/models，返回模型 id 列表（标准 OpenAI 格式）。

    有 key 则带鉴权请求；无 key 先匿名尝试，401 时给明确提示（如 DeepSeek）。
    失败抛 LLMError / AuthError，不静默。
    """
    url = f"{provider.base_url.rstrip('/')}/models"
    headers = {"Accept": "application/json"}
    key = os.environ.get(provider.api_key_env)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError as e:
        raise LLMError(f"拉取模型列表失败（网络错误）: {e}", provider_id=provider.id) from e
    if resp.status_code == 401:
        raise AuthError(
            f"/models 需要鉴权，请在 data/config/secrets.toml 设置 {provider.api_key_env}",
            provider_id=provider.id,
        )
    if resp.status_code != 200:
        raise LLMError(
            f"/models 返回 HTTP {resp.status_code}: {resp.text[:200]}",
            provider_id=provider.id,
        )
    try:
        data = resp.json()
    except ValueError as e:
        raise LLMError(f"/models 响应不是合法 JSON: {e}", provider_id=provider.id) from e
    return [m["id"] for m in data.get("data", []) if m.get("id")]


# ---------- models.dev enrichment ----------


def modelsdev_load(data_dir: Path, *, refresh: bool = False) -> dict:
    """加载 models.dev api.json（带 7 天缓存）。

    refresh=True 强制重新下载。下载/解析失败时返回空 dict（enrichment 宽容降级，
    元数据留空不影响同步主流程）。
    """
    path = data_dir / "models-dev.json"
    if not refresh and path.exists():
        age = _dt.datetime.now().timestamp() - path.stat().st_mtime
        if age < MODELSDEV_CACHE_TTL:
            try:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (ValueError, OSError):
                logger.warning("models.dev 缓存损坏，重新下载")
    try:
        resp = httpx.get(MODELSDEV_URL, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.error(f"models.dev 下载失败: {e}")
        return {}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f)
        logger.info(f"models.dev 数据已缓存到 {path}")
    except OSError as e:
        logger.warning(f"models.dev 缓存写盘失败: {e}")
    return data


def enrich_model(provider_id: str, model_id: str, modelsdev: dict) -> LLMModel:
    """查 models.dev 生成带元数据的 LLMModel；未收录时 name/request_name=id。

    字段映射：name → name；limit.context → context_length；
    tool_call / reasoning / modalities 图像 → capabilities。
    """
    meta = modelsdev.get(provider_id, {}).get("models", {}).get(model_id) or {}
    name = meta.get("name") or model_id
    capabilities: list[str] = []
    if meta.get("tool_call"):
        capabilities.append("tools")
    if meta.get("reasoning"):
        capabilities.append("reasoning")
    input_modalities = (meta.get("modalities") or {}).get("input") or []
    if any("image" in str(m).lower() for m in input_modalities):
        capabilities.append("vision")
    context = None
    limit = meta.get("limit") or {}
    if limit.get("context"):
        context = int(limit["context"])
    return LLMModel(
        id=model_id,
        name=name,
        request_name=model_id,
        formats=[ApiFormat.CHAT],
        context_length=context,
        capabilities=capabilities,
    )


# ---------- 三方对比 ----------


@dataclass
class SyncDiff:
    """端点 vs 本地配置的对比结果。"""

    added: list[str]  # 云有本地无（添加候选）
    kept: list[str]  # 两边都有
    missing: list[str]  # 本地有云无（移除并记入缺失文件）


def compute_diff(provider: LLMProvider, endpoint_ids: list[str]) -> SyncDiff:
    """按白名单语义对比：仅端点新模型进入候选，缺失模型从配置移除。"""
    local = {m.id for m in provider.models}
    ep = set(endpoint_ids)
    return SyncDiff(
        added=[mid for mid in endpoint_ids if mid not in local],
        kept=[mid for mid in endpoint_ids if mid in local],
        missing=[m.id for m in provider.models if m.id not in ep],
    )


# ---------- 缺失记录（只读留档） ----------


@dataclass(frozen=True)
class MissingEntry:
    """一条缺失记录：模型曾配置但已从端点消失。"""

    provider: str
    model: str
    last_seen: str  # ISO 日期：首次确认它已从端点消失的同步日


def missing_file_path() -> Path:
    """缺失记录位置（data/state/llm-list-missing.json，机器维护、只读查看）。"""
    return paths.state_dir() / MISSING_FILE_NAME


def load_missing(path: Path | None = None) -> list[MissingEntry]:
    """读取缺失记录（JSON 数组）；文件缺失或损坏时返回空列表并记 warning。"""
    p = path or missing_file_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        logger.warning(f"缺失记录读取失败（{e}），按空处理")
        return []
    if not isinstance(data, list):
        logger.warning(f"缺失记录格式不是数组（{type(data).__name__}），按空处理")
        return []
    entries = [
        MissingEntry(
            provider=str(item.get("provider", "")),
            model=str(item["model"]),
            last_seen=str(item.get("last_seen", "")),
        )
        for item in data
        if isinstance(item, dict) and item.get("model") and item.get("provider")
    ]
    return sorted(entries, key=lambda e: (e.provider, e.model))


def save_missing(entries: list[MissingEntry], path: Path | None = None) -> None:
    """写缺失记录（按 provider + model 排序，保证重复同步后文件稳定）。"""
    p = path or missing_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {"provider": e.provider, "model": e.model, "last_seen": e.last_seen}
        for e in sorted(entries, key=lambda e: (e.provider, e.model))
    ]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_missing(
    provider_id: str,
    endpoint_ids: list[str],
    missing_ids: list[str],
    *,
    path: Path | None = None,
    today: _dt.date | None = None,
) -> list[MissingEntry]:
    """同步后更新缺失记录（幂等、跨提供方合并）。

    - 本次「本地有云无」的模型写入；已有条目保留首次记录的 ``last_seen``
    - 已回归端点的同提供方条目删除（不做自动恢复，模型回到端点即可重新添加）
    - 其他提供方的条目原样保留，重复同步不丢条目
    """
    today = today or _dt.date.today()
    endpoint = set(endpoint_ids)
    kept = [e for e in load_missing(path) if e.provider != provider_id or e.model not in endpoint]
    known = {(e.provider, e.model) for e in kept}
    kept.extend(
        MissingEntry(provider=provider_id, model=model, last_seen=today.isoformat())
        for model in sorted(set(missing_ids))
        if (provider_id, model) not in known
    )
    save_missing(kept, path=path)
    return load_missing(path)


# ---------- 同步计划与落盘 ----------


@dataclass
class SyncPlan:
    """一次 fetch 的完整同步计划（不落盘，供 UI/非 TTY 决定后 apply）。"""

    provider: LLMProvider
    endpoint_ids: list[str]
    diff: SyncDiff
    candidates: list[LLMModel]  # 添加候选 = 端点新增，带 enrichment 元数据


def plan_sync(provider: LLMProvider, endpoint_ids: list[str], modelsdev: dict) -> SyncPlan:
    """生成同步计划：对比 + 候选 enrichment。"""
    diff = compute_diff(provider, endpoint_ids)
    candidates = [enrich_model(provider.id, mid, modelsdev) for mid in sorted(diff.added)]
    return SyncPlan(provider=provider, endpoint_ids=endpoint_ids, diff=diff, candidates=candidates)


def config_to_dict(cfg: ProviderConfig) -> dict:
    """ProviderConfig → dict（供 tomli_w 序列化；None 值跳过）。"""
    providers: list[dict] = []
    for p in cfg.providers:
        models: list[dict] = []
        for m in p.models:
            d: dict = {
                "id": m.id,
                "name": m.name,
                "request_name": m.request_name,
                "formats": list(m.formats),
            }
            if m.context_length is not None:
                d["context_length"] = m.context_length
            if m.capabilities:
                d["capabilities"] = list(m.capabilities)
            if m.thinking_default is not None:
                d["thinking_default"] = m.thinking_default
            models.append(d)
        pd: dict = {
            "id": p.id,
            "name": p.name,
            "base_url": p.base_url,
            "api_key_env": p.api_key_env,
            "models": models,
        }
        if p.timeout != 30.0:
            pd["timeout"] = p.timeout
        if p.transport != "sdk":
            pd["transport"] = p.transport
        providers.append(pd)
    data: dict = {
        "default_provider_order": list(cfg.order),
        "providers": {"provider": providers},
    }
    if cfg.default_model:
        data["default_model"] = cfg.default_model
    return data


def write_providers(path: str | Path, cfg: ProviderConfig) -> None:
    """写回 providers.toml；写前备份为同目录 <原名>.bak 文件。"""
    p = Path(path)
    if p.exists():
        shutil.copy2(p, Path(f"{p}.bak"))
    with p.open("wb") as f:
        tomli_w.dump(config_to_dict(cfg), f)


def apply_sync(
    plan: SyncPlan,
    selected: list[str],
    *,
    cfg: ProviderConfig,
    providers_path: str | Path,
    keep: list[str] | None = None,
    missing_path: Path | None = None,
    today: _dt.date | None = None,
) -> list[MissingEntry]:
    """把勾选结果落盘：改 providers.toml + 更新缺失记录，返回当前缺失记录。

    selected：勾选的候选模型 id。
    keep：本地有云无但用户要求保留的模型 id（不移除、不记缺失）。
    """
    provider = plan.provider
    keep_ids = set(keep or [])

    # 1. 移除缺失模型（keep 的除外）
    provider.models = [
        m for m in provider.models if m.id not in plan.diff.missing or m.id in keep_ids
    ]

    # 2. 添加勾选候选（已存在则跳过）
    selected_set = set(selected)
    for m in plan.candidates:
        if m.id in selected_set and provider.get_model(m.id) is None:
            provider.models.append(m)

    # 3. 缺失记录（不含 keep）
    recorded = update_missing(
        provider.id,
        plan.endpoint_ids,
        [mid for mid in plan.diff.missing if mid not in keep_ids],
        path=missing_path,
        today=today,
    )

    # 4. 写回 providers.toml（含备份）
    write_providers(providers_path, cfg)
    return recorded


# ---------- 总线服务（供 WebUI 常驻服务调用的 /models 同步 + 缺失查看）----------
#
# 命名 `llm.fetch.*` / `llm.missing.*`，与 /models 同步的核心逻辑一一对应；
# 只暴露数据操作与只读查询，交互勾选 UI 由调用方（WebUI/CLI）负责。


def fetch_plan(pid: str) -> dict:
    """执行 fetch 审核全流程，返回可展示的同步计划摘要。

    流程：加载配置 → 定位提供方 → 拉 /models → models.dev enrichment → 生成计划。
    pid 不存在返回 {"error": ...}。
    """
    from aris.config import get_settings

    cfg = load_providers(get_settings().llm_providers_file)
    provider = next((p for p in cfg.providers if p.id == pid), None)
    if provider is None:
        return {"error": f"提供方 {pid} 不存在"}
    endpoint_ids = fetch_provider_models(provider)
    modelsdev = modelsdev_load(get_settings().data_dir)
    plan = plan_sync(provider, endpoint_ids, modelsdev)

    def _ctx(match: LLMModel) -> dict:
        """模型计划条目的展示上下文。"""
        return {
            "id": match.id,
            "name": match.name,
            "context": f"{match.context_length // 1000}K" if match.context_length else "-",
        }

    return {
        "provider_name": provider.name,
        "added": [_ctx(c) for c in plan.candidates],
        "kept": plan.diff.kept,
        "missing": plan.diff.missing,
    }


def fetch_apply(pid: str, selected: list[str]) -> None:
    """应用 fetch 结果：勾选候选写回 providers.toml + 更新缺失记录。

    基于执行时刻的最新状态重新拉取（与 CLI 行为一致），确保 apply 幂等。
    """
    from aris.config import get_settings

    settings = get_settings()
    cfg = load_providers(settings.llm_providers_file)
    provider = next((p for p in cfg.providers if p.id == pid), None)
    if provider is None:
        return
    endpoint_ids = fetch_provider_models(provider)
    modelsdev = modelsdev_load(settings.data_dir)
    plan = plan_sync(provider, endpoint_ids, modelsdev)
    apply_sync(
        plan,
        selected,
        cfg=cfg,
        providers_path=settings.llm_providers_file,
    )


def missing_list() -> list[MissingEntry]:
    """列出当前缺失模型记录（只读）。"""
    return load_missing()


def _register_bus_services() -> None:
    """注册 /models 同步相关总线服务（模块导入时调用）。"""
    from aris.core.bus import provide

    provide("llm.fetch.plan", fetch_plan)
    provide("llm.fetch.apply", fetch_apply)
    provide("llm.missing.list", missing_list)


_register_bus_services()
