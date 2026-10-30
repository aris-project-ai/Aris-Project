"""v0.4.4 W5：/models 同步后的「缺失记录」（退休 / 宽限期机制已退役）。

覆盖：
- `compute_diff` 的三分类；
- `update_missing` 写 JSON、幂等合并、跨提供方保留、回归后条目移除；
- `plan_sync` + `apply_sync`：缺失模型从配置移除并写入缺失记录，`keep` 例外；
- 记录文件缺失 / 损坏时宽容降级。
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from aris.core.llm.config import LLMModel, LLMProvider, ProviderConfig
from aris.core.llm.fetch import (
    apply_sync,
    compute_diff,
    load_missing,
    plan_sync,
    save_missing,
    update_missing,
)

_TODAY = dt.date(2026, 10, 30)


def _model(mid: str) -> LLMModel:
    return LLMModel(id=mid, name=mid, request_name=mid)


def _provider(*model_ids: str) -> LLMProvider:
    return LLMProvider(
        id="oc",
        name="OC",
        base_url="https://example.test/v1",
        api_key_env="OC_API_KEY",
        models=[_model(m) for m in model_ids],
    )


def _cfg(provider: LLMProvider) -> ProviderConfig:
    return ProviderConfig(
        providers=[provider],
        order=[provider.id],
        default_model=provider.models[0].id if provider.models else None,
    )


def test_compute_diff_three_way() -> None:
    """端点新增 / 保留 / 缺失三分类。"""
    diff = compute_diff(_provider("a", "b", "c"), ["b", "c", "d"])
    assert diff.added == ["d"]
    assert diff.kept == ["b", "c"]
    assert diff.missing == ["a"]


def test_update_missing_writes_json(tmp_path: Path) -> None:
    """缺失模型写入 JSON 数组（provider / model / last_seen）。"""
    path = tmp_path / "llm-list-missing.json"
    update_missing("oc", ["b"], ["a"], path=path, today=_TODAY)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == [{"provider": "oc", "model": "a", "last_seen": "2026-10-30"}]


def test_update_missing_is_idempotent(tmp_path: Path) -> None:
    """重复同步不丢条目、不重复、不改首次日期。"""
    path = tmp_path / "llm-list-missing.json"
    update_missing("oc", ["b"], ["a"], path=path, today=_TODAY)
    update_missing("oc", ["b"], ["a"], path=path, today=dt.date(2026, 11, 30))

    entries = load_missing(path)
    assert [(e.provider, e.model, e.last_seen) for e in entries] == [("oc", "a", "2026-10-30")]


def test_update_missing_keeps_other_providers(tmp_path: Path) -> None:
    """同步一个提供方不影响其他提供方的缺失记录。"""
    path = tmp_path / "llm-list-missing.json"
    save_missing([], path=path)
    update_missing("oc", [], ["a"], path=path, today=_TODAY)
    update_missing("ds", [], ["x"], path=path, today=_TODAY)
    update_missing("oc", [], ["a"], path=path, today=_TODAY)

    assert [(e.provider, e.model) for e in load_missing(path)] == [("ds", "x"), ("oc", "a")]


def test_update_missing_drops_recovered_model(tmp_path: Path) -> None:
    """模型回到端点后从缺失记录移除（不做自动恢复，只是不再算缺失）。"""
    path = tmp_path / "llm-list-missing.json"
    update_missing("oc", [], ["a"], path=path, today=_TODAY)
    update_missing("oc", ["a"], [], path=path, today=dt.date(2026, 11, 1))

    assert load_missing(path) == []


def test_apply_sync_removes_missing_and_records(tmp_path: Path) -> None:
    """缺失模型从 providers 移除并写入缺失记录；勾选候选被加入。"""
    provider = _provider("a", "b")
    cfg = _cfg(provider)
    providers_path = tmp_path / "providers.toml"
    missing_path = tmp_path / "llm-list-missing.json"

    plan = plan_sync(provider, ["b", "c"], {})
    recorded = apply_sync(
        plan,
        ["c"],
        cfg=cfg,
        providers_path=providers_path,
        missing_path=missing_path,
        today=_TODAY,
    )

    assert [m.id for m in provider.models] == ["b", "c"]
    assert [(e.provider, e.model) for e in recorded] == [("oc", "a")]
    assert providers_path.exists()
    assert [e.model for e in load_missing(missing_path)] == ["a"]


def test_apply_sync_keep_excludes_from_missing(tmp_path: Path) -> None:
    """keep 的模型既不从配置移除，也不进缺失记录。"""
    provider = _provider("a", "b")
    cfg = _cfg(provider)
    plan = plan_sync(provider, ["b"], {})

    recorded = apply_sync(
        plan,
        [],
        cfg=cfg,
        providers_path=tmp_path / "providers.toml",
        keep=["a"],
        missing_path=tmp_path / "llm-list-missing.json",
        today=_TODAY,
    )

    assert [m.id for m in provider.models] == ["a", "b"]
    assert recorded == []


def test_plan_sync_enriches_candidates() -> None:
    """新增候选带 models.dev 元数据；无元数据时 id 兜底。"""
    modelsdev = {
        "oc": {
            "models": {
                "c": {
                    "name": "Model C",
                    "limit": {"context": 128000},
                    "tool_call": True,
                }
            }
        }
    }
    plan = plan_sync(_provider("a"), ["a", "c", "d"], modelsdev)

    by_id = {m.id: m for m in plan.candidates}
    assert by_id["c"].name == "Model C"
    assert by_id["c"].context_length == 128000
    assert "tools" in by_id["c"].capabilities
    assert by_id["d"].name == "d"


def test_load_missing_tolerates_bad_file(tmp_path: Path) -> None:
    """记录文件损坏时按空处理，不抛异常。"""
    path = tmp_path / "llm-list-missing.json"
    path.write_text("not json", encoding="utf-8")
    assert load_missing(path) == []


def test_missing_entries_are_sorted(tmp_path: Path) -> None:
    """写盘按 provider + model 排序，重复同步后文件稳定。"""
    path = tmp_path / "llm-list-missing.json"
    update_missing("oc", [], ["z", "a"], path=path, today=_TODAY)
    assert [e.model for e in load_missing(path)] == ["a", "z"]
